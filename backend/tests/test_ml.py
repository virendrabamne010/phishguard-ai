"""
test_ml.py — Unit tests for the ML prediction engine.
Validates that the scoring model behaves correctly for real-world email patterns.
"""

import pytest
from app.ml.predict import predict_email, _score_to_label
from app.ml.preprocess import (
    is_sender_suspicious,
    is_sender_trusted,
    count_urgency_keywords,
    analyze_urls,
)


# ─────────────────────────────────────────────────────────────
# Trusted domain tests
# ─────────────────────────────────────────────────────────────
class TestTrustedDomains:
    def test_google_is_trusted(self):
        assert is_sender_trusted("noreply@google.com") is True

    def test_google_subdomain_is_trusted(self):
        assert is_sender_trusted("no-reply@accounts.google.com") is True

    def test_microsoft_365_is_trusted(self):
        """365.microsoft.com has '3' in it — should NOT be flagged as number-substitution."""
        assert is_sender_trusted("noreply@365.microsoft.com") is True

    def test_amazon_is_trusted(self):
        assert is_sender_trusted("order-update@amazon.com") is True

    def test_github_notifications_trusted(self):
        assert is_sender_trusted("notifications@github.com") is True

    def test_linkedin_is_trusted(self):
        assert is_sender_trusted("messages@linkedin.com") is True

    def test_unknown_domain_not_trusted(self):
        assert is_sender_trusted("admin@randomdomain123.xyz") is False


# ─────────────────────────────────────────────────────────────
# Suspicious sender tests
# ─────────────────────────────────────────────────────────────
class TestSuspiciousSender:
    def test_paypal_typosquat_flagged(self):
        suspicious, reason = is_sender_suspicious("noreply@paypa1.com")
        assert suspicious is True
        assert "paypal" in reason.lower()

    def test_amazon_typosquat_flagged(self):
        suspicious, _ = is_sender_suspicious("support@amaz0n-security.com")
        assert suspicious is True

    def test_official_name_from_gmail_flagged(self):
        suspicious, reason = is_sender_suspicious("paypal-support@gmail.com")
        assert suspicious is True

    def test_microsoft_365_NOT_flagged(self):
        """Critical regression test: 365.microsoft.com has digits but should NOT be suspicious."""
        suspicious, _ = is_sender_suspicious("noreply@365.microsoft.com")
        assert suspicious is False

    def test_ip_domain_flagged(self):
        suspicious, _ = is_sender_suspicious("admin@192.168.1.1")
        assert suspicious is True

    def test_normal_unknown_domain_not_flagged(self):
        """Unknown domain isn't automatically suspicious — just not trusted."""
        suspicious, _ = is_sender_suspicious("newsletter@somedomain.com")
        assert suspicious is False


# ─────────────────────────────────────────────────────────────
# Urgency keyword tests
# ─────────────────────────────────────────────────────────────
class TestUrgencyKeywords:
    def test_phishing_urgency_detected(self):
        text = "Your account will be locked. Failure to verify will result in suspension."
        count, found = count_urgency_keywords(text)
        assert count >= 1

    def test_normal_urgency_NOT_flagged(self):
        """Words like 'action required', 'update your info' are normal in real emails."""
        text = "Action required: Please update your information to continue using our service."
        count, found = count_urgency_keywords(text)
        # Should NOT trigger high-confidence phishing keywords
        assert count == 0

    def test_prize_scam_detected(self):
        text = "Congratulations! You have won a $1000 prize. Claim your prize now!"
        count, found = count_urgency_keywords(text)
        assert count >= 1


# ─────────────────────────────────────────────────────────────
# URL analysis tests
# ─────────────────────────────────────────────────────────────
class TestUrlAnalysis:
    def test_google_url_is_clean(self):
        result = analyze_urls(["https://accounts.google.com/signin"])
        assert len(result["clean"]) == 1
        assert len(result["suspicious"]) == 0

    def test_amazon_url_is_clean(self):
        result = analyze_urls(["https://www.amazon.com/dp/B08N5KWB9H"])
        assert len(result["clean"]) == 1
        assert len(result["suspicious"]) == 0

    def test_ip_url_is_suspicious(self):
        result = analyze_urls(["http://192.168.1.100/login.php"])
        assert len(result["suspicious"]) == 1
        assert len(result["clean"]) == 0

    def test_unknown_domain_counted_as_suspicious(self):
        result = analyze_urls(["http://verify-account-alert.com/click"])
        assert len(result["suspicious"]) >= 1


# ─────────────────────────────────────────────────────────────
# End-to-end prediction tests
# ─────────────────────────────────────────────────────────────
class TestPrediction:
    def test_google_email_is_legitimate(self):
        result = predict_email(
            subject="Your Google Account security alert",
            body="We noticed a new sign-in to your Google Account. If this was you, you can ignore this message. https://myaccount.google.com",
            sender="no-reply@accounts.google.com",
        )
        assert result["label"] == "legitimate", f"Score={result['risk_score']}, got {result['label']}"
        assert result["risk_score"] <= 35

    def test_amazon_order_is_legitimate(self):
        result = predict_email(
            subject="Your Amazon order has been delivered",
            body="Great news! Your package was delivered today. View your order at https://www.amazon.com/orders.",
            sender="shipment-tracking@amazon.com",
        )
        assert result["label"] == "legitimate", f"Score={result['risk_score']}, got {result['label']}"

    def test_obvious_phishing_is_flagged(self):
        result = predict_email(
            subject="URGENT: Your account will be suspended",
            body="Your account will be locked in 24 hours. Click here to verify: http://192.168.1.100/verify.php. Provide your bank account number and SSN immediately.",
            sender="security@paypa1-alerts.com",
        )
        assert result["label"] in ["suspicious", "phishing"], f"Score={result['risk_score']}, got {result['label']}"
        assert result["risk_score"] > 35

    def test_result_has_required_keys(self):
        result = predict_email(
            subject="Test", body="Test body", sender="test@example.com"
        )
        assert "risk_score" in result
        assert "label" in result
        assert "flagged_reasons" in result
        assert "suspicious_keywords" in result

    def test_score_within_range(self):
        result = predict_email(
            subject="Test", body="Test body", sender="test@example.com"
        )
        assert 0 <= result["risk_score"] <= 100


# ─────────────────────────────────────────────────────────────
# Label threshold tests
# ─────────────────────────────────────────────────────────────
class TestLabelThresholds:
    def test_score_0_is_legitimate(self):
        assert _score_to_label(0) == "legitimate"

    def test_score_35_is_legitimate(self):
        assert _score_to_label(35) == "legitimate"

    def test_score_36_is_suspicious(self):
        assert _score_to_label(36) == "suspicious"

    def test_score_65_is_suspicious(self):
        assert _score_to_label(65) == "suspicious"

    def test_score_66_is_phishing(self):
        assert _score_to_label(66) == "phishing"

    def test_score_100_is_phishing(self):
        assert _score_to_label(100) == "phishing"
