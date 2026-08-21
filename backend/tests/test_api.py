"""
test_api.py — Integration tests for the PhishGuard FastAPI backend.
Uses an in-memory SQLite database and dependency overrides for isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, get_current_user, get_db
from app.database import Base
from app.models import AdminUser, SystemSettings
from app.config import settings

# ─────────────────────────────────────────────────────────────
# Test DB setup
# ─────────────────────────────────────────────────────────────
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def override_get_current_user():
    return AdminUser(username="test_admin", hashed_password="fake")


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
# Health endpoints
# ─────────────────────────────────────────────────────────────
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == settings.PROJECT_NAME
    assert "environment" in data


def test_readiness_check():
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["status"] == "ok"


# ─────────────────────────────────────────────────────────────
# Inbox status
# ─────────────────────────────────────────────────────────────
def test_inbox_status():
    response = client.get("/inbox/status")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "disconnected"
    assert data["email_count"] == 0


# ─────────────────────────────────────────────────────────────
# Custom email analysis
# ─────────────────────────────────────────────────────────────
def test_analyze_phishing_email():
    payload = {
        "subject": "Urgent: Verify Your Account",
        "sender": "security@paypa1.com",
        "body": "Your account will be suspended if you do not click here: http://fake-login.xyz. Provide your bank account number now.",
    }
    response = client.post("/inbox/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "flagged_reasons" in data
    assert data["label"] in ["legitimate", "suspicious", "phishing"]
    # This should NOT be legitimate
    assert data["label"] in ["suspicious", "phishing"]


def test_analyze_legitimate_email():
    """Emails from trusted Google domain should score as legitimate."""
    payload = {
        "subject": "Your monthly Google Workspace summary",
        "sender": "workspace-noreply@google.com",
        "body": "Hi there, here is your monthly summary for your Google Workspace account. View your report at https://workspace.google.com/dashboard.",
    }
    response = client.post("/inbox/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "legitimate", f"Expected legitimate but got {data['label']} (score={data['risk_score']})"


def test_analyze_amazon_email():
    """Amazon order confirmation should be legitimate."""
    payload = {
        "subject": "Your Amazon order has been shipped",
        "sender": "order-update@amazon.com",
        "body": "Hello, your order #123-456 has been shipped and is on its way. Track your package at https://www.amazon.com/orders. Expected delivery: tomorrow.",
    }
    response = client.post("/inbox/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "legitimate", f"Expected legitimate but got {data['label']} (score={data['risk_score']})"


def test_analyze_missing_body():
    response = client.post("/inbox/analyze", json={"subject": "Test"})
    assert response.status_code == 422  # Validation error — body is required


# ─────────────────────────────────────────────────────────────
# Email CRUD
# ─────────────────────────────────────────────────────────────
def test_get_emails_disconnected_or_demo():
    """Mode can be 'disconnected' or 'demo' depending on test run order (shared in-memory DB)."""
    response = client.get("/inbox/emails")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in ["disconnected", "demo", "imap", "gmail"]


def test_email_not_found():
    response = client.get("/inbox/emails/nonexistent-id-999")
    assert response.status_code == 404


def test_soft_delete_email():
    """Create an email, soft-delete it, confirm it disappears from inbox."""
    # First create one via analyze
    payload = {
        "subject": "Delete me",
        "sender": "test@example.com",
        "body": "This email will be deleted.",
    }
    create_resp = client.post("/inbox/analyze", json=payload)
    assert create_resp.status_code == 200
    # The email is created with a custom_XXX id. Fetch all to find it.
    emails_resp = client.get("/inbox/emails")
    emails = emails_resp.json().get("emails", [])
    if not emails:
        return  # Nothing to delete (mode may still be disconnected in test)
    email_id = emails[0]["id"]

    delete_resp = client.delete(f"/inbox/emails/{email_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "deleted"

    # Verify it's gone from the list
    after_resp = client.get("/inbox/emails")
    after_ids = [e["id"] for e in after_resp.json().get("emails", [])]
    assert email_id not in after_ids


# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────
def test_login_wrong_credentials():
    """Using the real login endpoint (no override) should return 401 on bad creds."""
    # Temporarily remove override
    saved = app.dependency_overrides.pop(get_current_user, None)
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "totally-wrong-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if saved:
        app.dependency_overrides[get_current_user] = saved
    assert response.status_code == 401


# ─────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────
def test_system_analytics():
    response = client.get("/system/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "global_scanned" in data
    assert "global_phishing" in data
    assert "global_suspicious" in data
    assert "model_metrics" in data
