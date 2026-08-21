/**
 * API Client — Typed fetch wrappers with error handling & timeout control.
 * Environment-aware base URL resolution.
 * Includes auto-reconnecting WebSocket with exponential backoff.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------
export function getToken() {
  return localStorage.getItem("phishguard_token");
}

export function getRefreshToken() {
  return localStorage.getItem("phishguard_refresh_token");
}

export function setTokens(access, refresh) {
  localStorage.setItem("phishguard_token", access);
  if (refresh) localStorage.setItem("phishguard_refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("phishguard_token");
  localStorage.removeItem("phishguard_refresh_token");
}

// ---------------------------------------------------------------------------
// WebSocket URL builder
// ---------------------------------------------------------------------------
export function getWebSocketUrl() {
  const token = getToken();
  let wsBase = API_BASE.startsWith("https")
    ? API_BASE.replace("https", "wss")
    : API_BASE.replace("http", "ws");

  const url = `${wsBase}/ws`;
  return token ? `${url}?token=${encodeURIComponent(token)}` : url;
}

// ---------------------------------------------------------------------------
// Reconnecting WebSocket
// Creates a WebSocket that automatically reconnects with exponential backoff.
// Returns an object with: { close(), onmessage, onstatuschange }
// ---------------------------------------------------------------------------
export function createReconnectingWebSocket(onMessage, onStatusChange) {
  let ws = null;
  let retryCount = 0;
  let closed = false;
  const MAX_RETRY_DELAY_MS = 30000; // cap at 30s

  function connect() {
    if (closed) return;

    onStatusChange?.("connecting");
    const url = getWebSocketUrl();

    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      retryCount = 0;
      onStatusChange?.("connected");
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        onMessage?.(payload);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      // onerror always fires before onclose — no action needed here
    };

    ws.onclose = (_event) => {
      if (closed) return;
      onStatusChange?.("reconnecting");
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (closed) return;
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
    const delay = Math.min(1000 * Math.pow(2, retryCount), MAX_RETRY_DELAY_MS);
    retryCount++;
    setTimeout(connect, delay);
  }

  connect();

  return {
    close() {
      closed = true;
      ws?.close();
      onStatusChange?.("disconnected");
    },
  };
}

// ---------------------------------------------------------------------------
// HTTP fetch wrapper
// ---------------------------------------------------------------------------
let _isRefreshing = false;
let _refreshSubscribers = [];

function onTokenRefreshed(token) {
  _refreshSubscribers.forEach((cb) => cb(token));
  _refreshSubscribers = [];
}

async function tryRefreshToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

async function fetchWithTimeout(resource, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const token = getToken();
    const headers = {
      "Content-Type": "application/json",
      ...options.headers,
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(resource, {
      ...options,
      signal: controller.signal,
      headers,
    });

    clearTimeout(timer);

    // Handle token expiry — try refresh once, but ONLY for authenticated requests.
    // A 401 on an unauthenticated call (e.g. wrong IMAP/admin credentials) is a real
    // error and must surface its message instead of logging the user out.
    const hadToken = Boolean(token);
    const isAuthEndpoint = resource.includes("/auth/login") || resource.includes("/auth/refresh");

    if (response.status === 401 && hadToken && !isAuthEndpoint) {
      if (!_isRefreshing) {
        _isRefreshing = true;
        const newToken = await tryRefreshToken();
        _isRefreshing = false;

        if (newToken) {
          onTokenRefreshed(newToken);
          // Retry original request with new token
          return fetchWithTimeout(resource, options, timeoutMs);
        } else {
          clearTokens();
          window.location.href = "/";
          throw new Error("Session expired. Please log in again.");
        }
      } else {
        // Wait for refresh to complete
        return new Promise((resolve) => {
          _refreshSubscribers.push(() => {
            resolve(fetchWithTimeout(resource, options, timeoutMs));
          });
        });
      }
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const msg = errorData.error || errorData.detail || `HTTP error! Status: ${response.status}`;
      throw new Error(msg);
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timer);
    if (error.name === "AbortError") {
      throw new Error("Request timed out. Please check if the backend server is running.");
    }
    throw error;
  }
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);

  const response = await fetchWithTimeout(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
  return response;
}

// ---------------------------------------------------------------------------
// Inbox
// ---------------------------------------------------------------------------
export async function getStatus() {
  return fetchWithTimeout(`${API_BASE}/inbox/status`);
}

export async function activateDemo() {
  return fetchWithTimeout(`${API_BASE}/inbox/demo`, { method: "POST" });
}

export async function connectGmail() {
  return fetchWithTimeout(`${API_BASE}/inbox/connect`);
}

export async function fetchGmailEmails() {
  return fetchWithTimeout(`${API_BASE}/inbox/fetch`, { method: "POST" });
}

export async function connectImap(email, password, provider = "gmail", imap_host = null, imap_port = 993) {
  return fetchWithTimeout(`${API_BASE}/inbox/imap/connect`, {
    method: "POST",
    body: JSON.stringify({ email, password, provider, imap_host, imap_port }),
  });
}

export async function refreshImapEmails() {
  return fetchWithTimeout(`${API_BASE}/inbox/imap/refresh`, { method: "POST" });
}

export async function backfillImapHistory(days = 10) {
  return fetchWithTimeout(`${API_BASE}/inbox/imap/backfill?days=${days}`, { method: "POST" });
}

export async function disconnectImap() {
  return fetchWithTimeout(`${API_BASE}/inbox/imap/disconnect`, { method: "POST" });
}

export async function getEmails() {
  return fetchWithTimeout(`${API_BASE}/inbox/emails`);
}

export async function getEmailDetail(id) {
  return fetchWithTimeout(`${API_BASE}/inbox/emails/${id}`);
}

export async function deleteEmail(emailId) {
  return fetchWithTimeout(`${API_BASE}/inbox/emails/${emailId}`, { method: "DELETE" });
}

export async function reportEmail(id) {
  return fetchWithTimeout(`${API_BASE}/inbox/emails/${id}/report`, { method: "POST" });
}

export async function analyzeCustomEmail(data) {
  return fetchWithTimeout(`${API_BASE}/inbox/analyze`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------
export async function getSystemAnalytics() {
  return fetchWithTimeout(`${API_BASE}/system/analytics`);
}

export async function getDatabaseDump() {
  return fetchWithTimeout(`${API_BASE}/system/database/dump`);
}

export async function getGmailSetupStatus() {
  return fetchWithTimeout(`${API_BASE}/health/gmail-setup`);
}

export async function searchEmails(query = "", label = "") {
  const params = new URLSearchParams();
  if (query) params.append("q", query);
  if (label) params.append("label", label);
  return fetchWithTimeout(`${API_BASE}/inbox/emails/search?${params.toString()}`);
}

export async function changePassword(currentPassword, newPassword) {
  return fetchWithTimeout(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export async function getAuditLog(limit = 100) {
  return fetchWithTimeout(`${API_BASE}/system/audit-log?limit=${limit}`);
}

// ---------------------------------------------------------------------------
// Authenticated exports (download via fetch with JWT, not plain <a> links)
// ---------------------------------------------------------------------------
export async function downloadExport(format = "csv") {
  const endpoint = format === "json" ? "system/export/json" : "system/export/csv";
  const token = getToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);

  try {
    const response = await fetch(`${API_BASE}/${endpoint}`, {
      signal: controller.signal,
      headers: {
        Authorization: token ? `Bearer ${token}` : "",
      },
    });
    clearTimeout(timer);

    if (response.status === 401) {
      // Try token refresh
      const newToken = await tryRefreshToken();
      if (!newToken) {
        clearTokens();
        window.location.href = "/";
        throw new Error("Session expired. Please log in again.");
      }
      // Retry with new token
      return downloadExport(format);
    }

    if (!response.ok) {
      throw new Error(`Export failed: HTTP ${response.status}`);
    }

    const blob = await response.blob();
    const filename = format === "json" ? "phishguard_report.json" : "phishguard_report.csv";
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  } catch (error) {
    clearTimeout(timer);
    if (error.name === "AbortError") {
      throw new Error("Export timed out.");
    }
    throw error;
  }
}
