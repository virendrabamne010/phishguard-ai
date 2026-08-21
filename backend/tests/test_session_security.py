import json

from app import main
from app.config import settings


def test_imap_session_is_encrypted_at_rest(tmp_path):
    original_path = settings.IMAP_SESSION_PATH
    try:
        settings.IMAP_SESSION_PATH = tmp_path / "imap_session.json"

        main._save_imap_session(
            email="student@example.com",
            password="SuperSecretAppPassword",
            provider="gmail",
            host="imap.gmail.com",
            port=993,
        )

        raw_content = settings.IMAP_SESSION_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw_content)

        assert parsed["encrypted"] is True
        assert "SuperSecretAppPassword" not in raw_content

        loaded = main._load_imap_session()
        assert loaded is not None
        assert loaded["password"] == "SuperSecretAppPassword"
        assert loaded["email"] == "student@example.com"
    finally:
        settings.IMAP_SESSION_PATH = original_path
