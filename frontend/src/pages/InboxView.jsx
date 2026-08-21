/**
 * InboxView — Main screen showing list of emails with risk scores.
 * Live updates via single long-lived WebSocket (mount-only lifecycle),
 * plus stats_updated refetch and a visibility-aware fallback poll.
 * Header carries a premium account chip (connected mailbox profile + actions).
 */

import { useState, useEffect, useRef } from "react";
import toast from "react-hot-toast";
import ConnectButton from "../components/ConnectButton";
import RiskScoreBadge from "../components/RiskScoreBadge";
import {
  getStatus, activateDemo, connectGmail, fetchGmailEmails,
  analyzeCustomEmail, connectImap, deleteEmail,
  refreshImapEmails, disconnectImap, backfillImapHistory,
  createReconnectingWebSocket, searchEmails,
} from "../api/client";
import PropTypes from "prop-types";
import { Loader2 } from "lucide-react";

// IMAP provider presets
const IMAP_PROVIDERS = [
  { value: "gmail",   label: "Gmail",    host: "imap.gmail.com",          port: 993, placeholder: "your.name@gmail.com",    hint: "Use a 16-char Google App Password (not your regular password)" },
  { value: "outlook", label: "Outlook",  host: "imap-mail.outlook.com",   port: 993, placeholder: "your.name@outlook.com",  hint: "Use your regular Outlook password or App Password if 2FA is on" },
  { value: "yahoo",   label: "Yahoo",    host: "imap.mail.yahoo.com",     port: 993, placeholder: "your.name@yahoo.com",     hint: "Generate an App Password from Yahoo Account Security settings" },
  { value: "hotmail", label: "Hotmail",  host: "imap-mail.outlook.com",   port: 993, placeholder: "your.name@hotmail.com",  hint: "Same server as Outlook — use your Hotmail password" },
  { value: "zoho",    label: "Zoho",     host: "imap.zoho.com",           port: 993, placeholder: "your.name@zoho.com",     hint: "Use your Zoho account password" },
  { value: "custom",  label: "Custom…",  host: "",                        port: 993, placeholder: "your@email.com",          hint: "Enter your IMAP server host and port below" },
];

const PROVIDER_LABELS = {
  gmail: "Gmail", outlook: "Outlook", yahoo: "Yahoo",
  hotmail: "Hotmail", zoho: "Zoho", custom: "IMAP",
};

export default function InboxView({ onSelectEmail }) {
  const [mode, setMode] = useState("disconnected");
  const [account, setAccount] = useState(null); // { email, provider }
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [wsStatus, setWsStatus] = useState("connecting");

  // Custom analyze modal state
  const [showModal, setShowModal] = useState(false);
  const [customSubject, setCustomSubject] = useState("");
  const [customSender, setCustomSender] = useState("");
  const [customBody, setCustomBody] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  // IMAP Connect modal state
  const [showImapModal, setShowImapModal] = useState(false);
  const [imapProvider, setImapProvider] = useState("gmail");
  const [imapEmail, setImapEmail] = useState("");
  const [imapPassword, setImapPassword] = useState("");
  const [imapCustomHost, setImapCustomHost] = useState("");
  const [imapCustomPort, setImapCustomPort] = useState(993);
  const [imapConnecting, setImapConnecting] = useState(false);
  const [showImapPassword, setShowImapPassword] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [backfilling, setBackfilling] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [filterLabel, setFilterLabel] = useState("");

  const [menuOpen, setMenuOpen] = useState(false);

  const wsRef = useRef(null);
  const statsDebounceRef = useRef(null);
  const menuRef = useRef(null);

  // Refs mirror latest values so mount-only listeners never go stale
  const filtersRef = useRef({ q: "", label: "" });
  filtersRef.current = { q: searchQuery, label: filterLabel };
  const modeRef = useRef(mode);
  modeRef.current = mode;

  const selectedProvider = IMAP_PROVIDERS.find((p) => p.value === imapProvider) || IMAP_PROVIDERS[0];

  async function fetchList(q = filtersRef.current.q, label = filtersRef.current.label) {
    try {
      const data = await searchEmails(q, label);
      setEmails(data.emails || []);
      return true;
    } catch {
      return false;
    }
  }

  async function checkStatus() {
    try {
      const data = await getStatus();
      setMode(data.mode);
      setAccount(
        data.connected_email
          ? { email: data.connected_email, provider: data.provider || "imap" }
          : null
      );
      if (data.mode !== "disconnected") {
        fetchList();
      } else {
        setEmails([]);
      }
    } catch {
      // Backend not running
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("auth") === "success") {
      window.history.replaceState({}, "", "/");
      handleGmailFetch();
    } else {
      checkStatus();
    }

    wsRef.current = createReconnectingWebSocket(
      (payload) => {
        if (payload.event === "new_email") {
          const newEmail = payload.data;
          const q = filtersRef.current.q.toLowerCase();
          const activeLabel = filtersRef.current.label;

          const queryMatch =
            !q ||
            newEmail.subject?.toLowerCase().includes(q) ||
            newEmail.sender?.toLowerCase().includes(q);
          const labelMatch = !activeLabel || newEmail.label === activeLabel;

          if (queryMatch && labelMatch) {
            setEmails((prev) => {
              if (prev.some((e) => e.id === newEmail.id)) return prev;
              return [{ ...newEmail, is_new: true }, ...prev];
            });
          }

          if (newEmail.label === "phishing") {
            toast.error(`🚨 Phishing: ${newEmail.subject}`);
          } else if (newEmail.label === "suspicious") {
            toast(`⚠️ Suspicious: ${newEmail.subject}`, { icon: "⚠️" });
          } else {
            toast.success(`✓ Legitimate: ${newEmail.subject}`);
          }
        }

        if (payload.event === "stats_updated") {
          clearTimeout(statsDebounceRef.current);
          statsDebounceRef.current = setTimeout(() => fetchList(), 800);
        }
      },
      (status) => setWsStatus(status)
    );

    // Fallback safety net: silently resync even if the socket drops
    const pollId = setInterval(() => {
      if (document.visibilityState === "visible" && modeRef.current !== "disconnected") {
        fetchList();
      }
    }, 25000);

    return () => {
      clearInterval(pollId);
      clearTimeout(statsDebounceRef.current);
      wsRef.current?.close();
    };
  }, []);

  // Close account menu on outside click / Escape
  useEffect(() => {
    if (!menuOpen) return;
    function onClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  // Debounced re-search while typing
  useEffect(() => {
    if (mode === "disconnected") return;
    const timeoutId = setTimeout(() => {
      fetchList(searchQuery, filterLabel);
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [searchQuery, filterLabel, mode]);

  async function handleDemo() {
    setLoading(true);
    setError(null);
    try {
      await activateDemo();
      setMode("demo");
      setEmails([]);
      toast("Demo activated! Background processing started.", { icon: "🚀" });
    } catch {
      setError("Failed to load demo data. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  async function handleGmail() {
    setLoading(true);
    setError(null);
    try {
      const data = await connectGmail();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      const msg = err.message || "";
      if (msg.toLowerCase().includes("credentials") || msg.toLowerCase().includes("oauth")) {
        setError("Gmail OAuth not configured. Follow the setup guide that appears when you click 'Connect Gmail Account', or use IMAP (supports Gmail, Outlook, Yahoo) instead.");
      } else {
        setError("Gmail connection failed. Try using IMAP with an App Password instead — it works without any Cloud Console setup.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleGmailFetch() {
    setLoading(true);
    try {
      const response = await fetchGmailEmails();
      setMode("gmail");
      if (response.email_count > 0) {
        toast(`Found ${response.email_count} new emails. Analyzing in background...`, { icon: "⏳" });
      } else {
        toast.success("Inbox is already up to date!");
      }
    } catch {
      setError("Failed to fetch Gmail emails.");
    } finally {
      setLoading(false);
    }
  }

  async function handleImapSubmit(e) {
    e.preventDefault();
    if (!imapEmail.trim() || !imapPassword.trim()) return;

    setImapConnecting(true);
    setError(null);
    try {
      const provider = imapProvider;
      const imap_host = provider === "custom" ? imapCustomHost || null : null;
      const imap_port = provider === "custom" ? imapCustomPort : 993;

      const response = await connectImap(imapEmail, imapPassword, provider, imap_host, imap_port);
      setMode("imap");
      setShowImapModal(false);
      setImapPassword(""); // Clear password from state

      await checkStatus();

      if (response.email_count > 0) {
        toast(`Connected! Found ${response.email_count} new emails. Analyzing...`, { icon: "⏳" });
      } else {
        toast.success("Connected! Inbox is up to date.");
      }
    } catch (err) {
      toast.error(err.message || "Failed to connect via IMAP. Check credentials and App Password.");
    } finally {
      setImapConnecting(false);
    }
  }

  async function handleRefresh(silent = false) {
    if (!silent) setRefreshing(true);
    setError(null);
    try {
      const response = await refreshImapEmails();
      if (response.email_count > 0) {
        toast(`Found ${response.email_count} new emails. Analyzing in background...`, { icon: "⏳" });
        setTimeout(async () => {
          await fetchList();
        }, 1500);
      } else if (!silent) {
        toast.success("Inbox is up to date.");
      }
    } catch (err) {
      if (!silent) {
        setError(err.message || "Failed to refresh emails.");
        toast.error(err.message || "Failed to refresh emails.");
      }
    } finally {
      if (!silent) setRefreshing(false);
    }
  }

  async function handleBackfill() {
    setBackfilling(true);
    setError(null);
    try {
      const response = await backfillImapHistory(10);
      if (response.email_count > 0) {
        toast(`Found ${response.email_count} historical emails. Analyzing in background...`, { icon: "⏳" });
        setTimeout(async () => {
          await fetchList();
        }, 2000);
      } else {
        toast.success("No historical emails found.");
      }
    } catch (err) {
      setError(err.message || "Failed to scan historical emails.");
    } finally {
      setBackfilling(false);
    }
  }

  async function handleDisconnect() {
    if (!window.confirm("Disconnect IMAP and stop live email monitoring?")) return;
    try {
      await disconnectImap();
      setMode("disconnected");
      setAccount(null);
      setEmails([]);
      setMenuOpen(false);
      toast.success("IMAP disconnected. Live monitoring stopped.");
    } catch (err) {
      toast.error(err.message || "Failed to disconnect IMAP.");
    }
  }

  async function handleCustomSubmit(e) {
    e.preventDefault();
    if (!customBody.trim()) return;

    setAnalyzing(true);
    try {
      await analyzeCustomEmail({
        subject: customSubject || "No Subject",
        sender: customSender || "unknown@domain.com",
        body: customBody,
      });

      setMode((m) => (m === "disconnected" ? "demo" : m));
      setShowModal(false);
      setCustomSubject("");
      setCustomSender("");
      setCustomBody("");
      toast.success("Custom email scan submitted successfully.");
    } catch (err) {
      toast.error(err.message || "Failed to analyze the custom email.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleDeleteEmail(e, emailId) {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this email?")) return;

    try {
      await deleteEmail(emailId);
      setEmails((prev) => prev.filter((email) => email.id !== emailId));
      toast.success("Email deleted.");
    } catch {
      toast.error("Failed to delete email.");
    }
  }

  const stats = {
    total: emails.length,
    phishing: emails.filter((e) => e.label === "phishing").length,
    suspicious: emails.filter((e) => e.label === "suspicious").length,
    legitimate: emails.filter((e) => e.label === "legitimate").length,
  };

  const wsStatusConfig = {
    connected:    { color: "text-emerald-400", dot: "bg-emerald-400", label: "Live", pulse: true },
    connecting:   { color: "text-amber-400",   dot: "bg-amber-400",   label: "Connecting", pulse: true },
    reconnecting: { color: "text-amber-400",   dot: "bg-amber-400",   label: "Syncing…", pulse: true },
    disconnected: { color: "text-red-400",     dot: "bg-red-400",     label: "Offline", pulse: false },
  };
  const wsConfig = wsStatusConfig[wsStatus] || wsStatusConfig.connecting;

  const providerLabel = account
    ? (PROVIDER_LABELS[account.provider] || "IMAP")
    : mode === "demo" ? "Demo" : mode === "gmail" ? "Gmail OAuth" : null;
  const avatarLetter = account?.email?.charAt(0)?.toUpperCase() || "P";
  const isConnectedMailbox = Boolean(account);

  return (
    <div className="min-h-screen">
      {/* Premium gradient accent */}
      <div className="h-[2px] bg-gradient-to-r from-transparent via-indigo-500/70 to-transparent" />

      {/* Header */}
      <header className="border-b border-slate-800/70 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-3">

          {/* Live status */}
          <div className={`flex items-center gap-2 text-xs font-semibold tracking-wide ${wsConfig.color}`}>
            <span className={`w-2 h-2 rounded-full ${wsConfig.dot} ${wsConfig.pulse ? "animate-pulse" : ""}`} />
            {wsConfig.label}
            {mode !== "disconnected" && (
              <span className="hidden sm:inline text-slate-500 font-normal">· monitoring</span>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            {/* Primary action */}
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-xs font-bold hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-950/50"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 4v16m8-8H4" />
              </svg>
              Scan Email
            </button>

            {mode === "disconnected" ? (
              <button
                onClick={() => setShowImapModal(true)}
                className="px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-600/50 text-slate-200 hover:bg-slate-700/60 text-xs font-semibold transition-all"
              >
                Connect Mailbox
              </button>
            ) : (
              /* ---- Account chip ---- */
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => isConnectedMailbox || mode === "demo" ? setMenuOpen((o) => !o) : setShowImapModal(true)}
                  className="flex items-center gap-2.5 pl-1.5 pr-2.5 py-1.5 rounded-full bg-slate-800/50 border border-slate-700/60 hover:border-slate-600 hover:bg-slate-800/80 transition-all group"
                  title={account?.email || "Connect a mailbox"}
                >
                  <span className={`relative w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold shadow-md ${isConnectedMailbox ? "" : "opacity-80"}`}>
                    {avatarLetter}
                    <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-slate-900" />
                  </span>
                  <span className="hidden md:flex flex-col items-start leading-tight">
                    <span className="text-xs font-semibold text-slate-100 max-w-[170px] truncate">
                      {account?.email || "Demo workspace"}
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium">
                      {providerLabel ? `${providerLabel}${mode === "imap" ? " · IMAP" : ""}` : "Not connected"}
                    </span>
                  </span>
                  {(isConnectedMailbox || mode === "demo") && (
                    <svg className={`w-3.5 h-3.5 text-slate-500 group-hover:text-slate-300 transition-all ${menuOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  )}
                </button>

                {/* Dropdown */}
                {menuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-60 rounded-2xl border border-slate-700/60 bg-slate-900 shadow-2xl shadow-black/60 overflow-hidden fade-in">
                    <div className="px-4 py-3 border-b border-slate-800/80 bg-slate-900/95">
                      <p className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">Signed-in mailbox</p>
                      <p className="text-sm font-semibold text-white truncate mt-0.5">{account?.email || "Demo workspace"}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        {providerLabel} · real-time protection active
                      </p>
                    </div>

                    <div className="py-1.5">
                      <button
                        onClick={() => { setMenuOpen(false); handleRefresh(); }}
                        disabled={refreshing}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium text-slate-300 hover:bg-slate-800/70 hover:text-white transition-colors disabled:opacity-50"
                      >
                        {refreshing ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : (
                          <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                        )}
                        Check for new mail
                      </button>

                      {mode === "imap" && (
                        <button
                          onClick={() => { setMenuOpen(false); handleBackfill(); }}
                          disabled={backfilling}
                          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium text-slate-300 hover:bg-slate-800/70 hover:text-white transition-colors disabled:opacity-50"
                        >
                          {backfilling ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : (
                            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          )}
                          Scan history (last 10 days)
                        </button>
                      )}
                    </div>

                    {mode === "imap" && (
                      <div className="border-t border-slate-800/80 py-1.5">
                        <button
                          onClick={handleDisconnect}
                          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                          Disconnect mailbox
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm fade-in">
            {error}
          </div>
        )}

        {mode === "disconnected" && (
          <div className="glass-card p-8 fade-in">
            <ConnectButton onDemo={handleDemo} onGmail={handleGmail} onImap={() => setShowImapModal(true)} loading={loading} />
          </div>
        )}

        {mode !== "disconnected" && (
          <>
            <div className="grid grid-cols-4 gap-3 mb-6 fade-in">
              <div className="glass-card p-4 text-center">
                <div className="text-2xl font-bold text-white">{stats.total}</div>
                <div className="text-xs text-slate-400 mt-1">Total Emails</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-2xl font-bold text-red-400">{stats.phishing}</div>
                <div className="text-xs text-slate-400 mt-1">Phishing</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-2xl font-bold text-amber-400">{stats.suspicious}</div>
                <div className="text-xs text-slate-400 mt-1">Suspicious</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-2xl font-bold text-emerald-400">{stats.legitimate}</div>
                <div className="text-xs text-slate-400 mt-1">Legitimate</div>
              </div>
            </div>

            <div className="glass-card overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-700/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/50">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-slate-300">
                    Threat Inbox
                  </h2>
                  <span className="text-slate-500 text-xs font-normal bg-slate-800 px-2 py-0.5 rounded-full">
                    {emails.length} analyzed
                  </span>
                  {refreshing && <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" />}
                </div>

                <div className="flex items-center gap-3">
                  {/* Search Bar */}
                  <div className="relative">
                    <svg className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      type="text"
                      placeholder="Search emails..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 pr-4 py-2 w-full sm:w-64 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery("")}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    )}
                  </div>

                  {/* Filter Dropdown */}
                  <select
                    value={filterLabel}
                    onChange={(e) => setFilterLabel(e.target.value)}
                    className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-colors appearance-none pr-8 relative"
                    style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`, backgroundRepeat: "no-repeat", backgroundPosition: "right 0.5rem center", backgroundSize: "1rem" }}
                  >
                    <option value="">All Risks</option>
                    <option value="phishing">Phishing</option>
                    <option value="suspicious">Suspicious</option>
                    <option value="legitimate">Legitimate</option>
                  </select>
                </div>
              </div>

              <div className="divide-y divide-slate-800/50 stagger-children">
                {emails.map((email) => (
                  <div
                    key={email.id}
                    onClick={() => onSelectEmail(email.id)}
                    className={`w-full text-left px-5 py-4 flex items-center gap-4 transition-all duration-200 cursor-pointer group
                      ${email.is_new ? "bg-slate-800/80 border-l-2 border-indigo-500" : "bg-transparent hover:bg-slate-800/30"}
                    `}
                  >
                    <div
                      className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        email.label === "phishing"
                          ? "bg-red-500 shadow-lg shadow-red-500/50"
                          : email.label === "suspicious"
                          ? "bg-amber-500 shadow-lg shadow-amber-500/50"
                          : "bg-emerald-500 shadow-lg shadow-emerald-500/50"
                      }`}
                    />
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0 text-slate-300 font-bold text-sm">
                      {email.sender.charAt(0).toUpperCase()}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-semibold text-white truncate text-sm">{email.sender}</span>
                      </div>
                      <div className="text-sm text-slate-300 font-medium truncate">{email.subject}</div>
                      <div className="text-xs text-slate-500 truncate mt-0.5">{email.snippet}</div>
                    </div>

                    <div className="flex-shrink-0 flex items-center gap-4">
                      <RiskScoreBadge score={email.risk_score} label={email.label} />

                      <button
                        onClick={(e) => handleDeleteEmail(e, email.id)}
                        className="p-2 text-slate-600 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                        title="Delete Email"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>

                      <svg className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </main>

      {/* Custom Email Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 fade-in">
          <div className="glass-card max-w-lg w-full p-6 relative">
            <h3 className="text-lg font-bold text-white mb-4">Scan Custom Email</h3>
            <form onSubmit={handleCustomSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Sender Email</label>
                <input
                  type="text"
                  placeholder="e.g. security@paypa1-alerts.com"
                  value={customSender}
                  onChange={(e) => setCustomSender(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Subject</label>
                <input
                  type="text"
                  placeholder="e.g. Urgent: Account Action Required"
                  value={customSubject}
                  onChange={(e) => setCustomSubject(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Email Body *</label>
                <textarea
                  rows={5}
                  required
                  placeholder="Paste raw email text here..."
                  value={customBody}
                  onChange={(e) => setCustomBody(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={analyzing}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 disabled:opacity-50"
                >
                  {analyzing ? "Analyzing..." : "Analyze Now"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* IMAP Connect Modal — Multi-Provider */}
      {showImapModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 fade-in">
          <div className="glass-card max-w-lg w-full p-8 relative">
            <h3 className="text-xl font-bold text-white mb-2">Connect Real Inbox via IMAP</h3>
            <p className="text-slate-400 text-sm mb-6">
              Stream live emails from your real inbox. Choose your email provider below.
            </p>

            <form onSubmit={handleImapSubmit} className="space-y-5">
              {/* Provider selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Email Provider</label>
                <div className="grid grid-cols-3 gap-2">
                  {IMAP_PROVIDERS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => setImapProvider(p.value)}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
                        imapProvider === p.value
                          ? "bg-indigo-600/20 border-indigo-500/60 text-indigo-300"
                          : "bg-slate-900/50 border-slate-700/50 text-slate-400 hover:border-slate-600"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                {/* Hint */}
                <p className="text-slate-500 text-xs mt-2">{selectedProvider.hint}</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder={selectedProvider.placeholder}
                  value={imapEmail}
                  onChange={(e) => setImapEmail(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                  {imapProvider === "gmail" ? "App Password" : "Password"}
                </label>
                <div className="relative">
                  <input
                    type={showImapPassword ? "text" : "password"}
                    required
                    placeholder={imapProvider === "gmail" ? "16-character App Password" : "Your email password"}
                    value={imapPassword}
                    onChange={(e) => setImapPassword(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowImapPassword(!showImapPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white focus:outline-none"
                  >
                    {showImapPassword ? (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Custom host/port — only shown when "Custom…" is selected */}
              {imapProvider === "custom" && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">IMAP Host</label>
                    <input
                      type="text"
                      required
                      placeholder="imap.yourdomain.com"
                      value={imapCustomHost}
                      onChange={(e) => setImapCustomHost(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Port</label>
                    <input
                      type="number"
                      value={imapCustomPort}
                      onChange={(e) => setImapCustomPort(Number(e.target.value))}
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowImapModal(false); setImapPassword(""); }}
                  className="px-5 py-2.5 rounded-xl bg-slate-800 text-slate-300 text-sm font-semibold hover:bg-slate-700 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={imapConnecting}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-500 disabled:opacity-50 transition-all shadow-lg shadow-indigo-600/20 flex items-center gap-2"
                >
                  {imapConnecting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {imapConnecting ? "Connecting..." : "Secure Connect"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

InboxView.propTypes = {
  onSelectEmail: PropTypes.func.isRequired,
};
