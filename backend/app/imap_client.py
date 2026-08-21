"""
imap_client.py — Connect to any IMAP server, fetch and parse emails.

Supports Gmail, Outlook, Yahoo, and custom IMAP servers.
"""

import imaplib
import email
from email.header import decode_header
import ssl
import datetime

# Provider presets — maps a friendly name to (host, port)
IMAP_PROVIDERS = {
    "gmail":   ("imap.gmail.com", 993),
    "outlook": ("imap-mail.outlook.com", 993),
    "yahoo":   ("imap.mail.yahoo.com", 993),
    "hotmail": ("imap-mail.outlook.com", 993),
    "zoho":    ("imap.zoho.com", 993),
    "protonmail": ("127.0.0.1", 1143),   # Requires ProtonMail Bridge locally
}

# Folders scanned per provider — INBOX plus the provider's junk/spam folder,
# because phishing mails often land there before users ever see them.
PROVIDER_FOLDERS = {
    "gmail": ["inbox", "[Gmail]/Spam"],
    "googlemail": ["inbox", "[Gmail]/Spam"],
    "outlook": ["inbox", "Junk"],
    "hotmail": ["inbox", "Junk"],
    "yahoo": ["inbox", "Bulk Mail"],
    "zoho": ["inbox"],
}

# ID tag per junk folder — keeps ids unique across folders (IMAP UIDs are
# only unique per mailbox/folder).
FOLDER_ID_TAGS = {
    "[Gmail]/Spam": "junk",
    "Junk": "junk",
    "Bulk Mail": "bulk",
}


def clean(text: str) -> str:
    """Sanitise text for safe storage."""
    if not text:
        return ""
    return "".join(c if c.isprintable() else " " for c in text)


def decode_mime_header(header: str) -> str:
    """Decode RFC 2047-encoded email headers."""
    if not header:
        return ""
    try:
        parts = decode_header(header)
        decoded_parts = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded_parts.append(str(part))
        return "".join(decoded_parts)
    except Exception:
        return str(header)


def _extract_body(msg) -> str:
    """Extract plain text body from an email message object."""
    body = ""

    if msg.is_multipart():
        # First pass: prefer text/plain
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="replace")
                        return body
                except Exception:
                    continue

        # Second pass: fall back to text/html and strip tags
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    import re
                    html = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    body = re.sub(r'<[^<]+>', ' ', html).strip()
                    body = re.sub(r'\s+', ' ', body).strip()
                    return body
                except Exception:
                    continue
    else:
        try:
            if msg.get_content_type() == "text/plain":
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
            elif msg.get_content_type() == "text/html":
                import re
                payload = msg.get_payload(decode=True)
                if payload:
                    html = payload.decode("utf-8", errors="replace")
                    body = re.sub(r'<[^<]+>', ' ', html).strip()
                    body = re.sub(r'\s+', ' ', body).strip()
        except Exception:
            pass

    return body


def fetch_imap_emails(
    email_address: str,
    password: str,
    limit: int = 20,
    provider: str = "gmail",
    imap_host: str | None = None,
    imap_port: int = 993,
    days_back: int | None = None,
) -> list:
    """
    Connect to an IMAP server and fetch recent emails.

    Args:
        email_address: User's email address.
        password: App password or IMAP password.
        limit: Maximum number of emails to fetch.
        provider: One of 'gmail', 'outlook', 'yahoo', 'hotmail', 'zoho', or 'custom'.
        imap_host: Custom IMAP host (used when provider='custom').
        imap_port: Custom IMAP port (used when provider='custom').

    Raises:
        Exception: On authentication or connection failure.
    """
    # Resolve host and port
    if imap_host:
        host, port = imap_host, imap_port
    else:
        host, port = IMAP_PROVIDERS.get(provider.lower(), IMAP_PROVIDERS["gmail"])

    context = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(host, port=port, ssl_context=context)

    try:
        mail.login(email_address, password)
    except imaplib.IMAP4.error as e:
        raise Exception(f"IMAP authentication failed for {email_address}: {str(e)}")

    folders = PROVIDER_FOLDERS.get(provider.lower(), ["inbox"])
    parsed_emails: list = []

    for folder in folders:
        try:
            status, _ = mail.select(folder)
        except Exception:
            continue  # Folder not available on this server — skip silently
        if status != "OK":
            continue

        # Use UID commands — UIDs are permanent per-mailbox identifiers.
        # Sequence numbers shift whenever mails are deleted, which previously
        # made new arrivals collide with stored ids and get skipped as dupes.
        if days_back:
            target_date = datetime.datetime.now() - datetime.timedelta(days=days_back)
            date_str = target_date.strftime("%d-%b-%Y")
            status, messages = mail.uid("SEARCH", None, f'SINCE "{date_str}"')
        else:
            status, messages = mail.uid("SEARCH", None, "ALL")
        if status != "OK":
            continue

        uid_list = messages[0].split()
        latest_uids = uid_list[-limit:] if len(uid_list) > limit else uid_list

        id_tag = FOLDER_ID_TAGS.get(folder, "")
        prefix = f"imap_{id_tag}_u" if id_tag else "imap_u"

        for uid in reversed(latest_uids):
            try:
                res, msg_data = mail.uid("FETCH", uid, "(RFC822)")
                if res != "OK":
                    continue

                for response_part in msg_data:
                    if not isinstance(response_part, tuple):
                        continue

                    msg = email.message_from_bytes(response_part[1])

                    subject = decode_mime_header(msg.get("Subject", ""))
                    sender = decode_mime_header(msg.get("From", ""))
                    date_hdr = msg.get("Date", "")

                    body = _extract_body(msg)
                    body = clean(body)
                    snippet = (body[:150] + "...") if len(body) > 150 else body

                    parsed_emails.append({
                        "id": f"{prefix}{uid.decode()}",
                        "subject": subject or "(No Subject)",
                        "sender": sender or "Unknown",
                        "date": date_hdr,
                        "snippet": snippet,
                        "body": body or "(Empty Body)",
                        "folder": folder,
                    })
            except Exception:
                # Skip malformed messages silently
                continue

    try:
        mail.logout()
    except Exception:
        pass

    return parsed_emails
