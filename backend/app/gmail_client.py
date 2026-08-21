"""
gmail_client.py — Gmail OAuth flow + email fetching.
Uses google-api-python-client for a single-user, local-only setup.
Requires credentials.json from Google Cloud Console (see README).
"""

import os
import base64
import json
from email.utils import parseaddr
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app.config import settings
from app.logger import logger

# Gmail API scopes — read-only
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_auth_url() -> str:
    """Generate the Google OAuth consent URL."""
    if not os.path.exists(settings.CREDENTIALS_PATH):
        raise FileNotFoundError(
            "credentials.json not found. Download it from Google Cloud Console. "
            "See README for instructions."
        )

    flow = Flow.from_client_secrets_file(
        settings.CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=settings.REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def handle_callback(authorization_code: str) -> bool:
    """Exchange the authorization code for tokens and save to token.json."""
    try:
        flow = Flow.from_client_secrets_file(
            settings.CREDENTIALS_PATH,
            scopes=SCOPES,
            redirect_uri=settings.REDIRECT_URI,
        )
        flow.fetch_token(code=authorization_code)
        creds = flow.credentials

        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes),
        }
        os.makedirs(settings.BASE_DIR, exist_ok=True)
        with open(settings.TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

        logger.info("Gmail token saved successfully.")
        return True
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return False


def is_connected() -> bool:
    """Check if we have a valid Gmail token."""
    return os.path.exists(settings.TOKEN_PATH)


def _get_gmail_service():
    """Build the Gmail API service using saved credentials."""
    if not os.path.exists(settings.TOKEN_PATH):
        raise FileNotFoundError("Not connected to Gmail. Run OAuth flow first.")

    with open(settings.TOKEN_PATH, "r") as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", SCOPES),
    )

    return build("gmail", "v1", credentials=creds)


def fetch_emails(max_results: int = 20) -> list:
    """
    Fetch recent emails from Gmail inbox.
    Returns list of dicts with id, subject, sender, snippet, body.
    """
    service = _get_gmail_service()

    # List messages
    results = service.users().messages().list(
        userId="me", maxResults=max_results, labelIds=["INBOX"]
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg_meta in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_meta["id"], format="full"
        ).execute()

        # Extract headers
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("subject", "(No Subject)")
        sender = headers.get("from", "Unknown")
        _, sender_email = parseaddr(sender)

        # Extract body
        body = _extract_body(msg.get("payload", {}))
        snippet = msg.get("snippet", "")

        emails.append({
            "id": msg_meta["id"],
            "subject": subject,
            "sender": sender_email or sender,
            "snippet": snippet,
            "body": body,
        })

    return emails


def _extract_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    body = ""

    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    elif payload.get("parts"):
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            if mime == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
            elif mime == "text/html" and part.get("body", {}).get("data") and not body:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            elif part.get("parts"):
                body = _extract_body(part)
                if body:
                    break

    return body
