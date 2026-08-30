"""
predict.py — Load trained model and predict phishing risk for emails.
Artifacts are loaded once at module import time for fast inference.

SCORING PHILOSOPHY:
- Trusted senders (google.com, amazon.com, etc.) get a 25-point bonus
- URLs from trusted CDNs/domains are not penalised
- Only HIGH-CONFIDENCE urgency phrases (unique to phishing) score points
- ML model has 60% weight, heuristics 40%
- Thresholds: legitimate ≤ 35, suspicious 36–65, phishing > 65
"""

import os
import logging
import numpy as np
import joblib
from scipy.sparse import hstack, csr_matrix
from .preprocess import (
    clean_text,
    extract_urls,
    analyze_urls,
    count_urgency_keywords,
    calc_caps_ratio,
    calc_punctuation_ratio,
    is_sender_suspicious,
    is_sender_trusted,
    is_free_mail_sender,
    detect_brand_impersonation,
    extract_handcrafted_features,
)

# ---------------------------------------------------------------------------
# Load model artifacts at module level (once, on import)
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ARTIFACTS_DIR = os.path.join(_BASE_DIR, "model_artifacts")

logger = logging.getLogger("phishguard.ml")

_model = None
_vectorizer = None


def _load_artifacts():
    global _model, _vectorizer
    model_path = os.path.join(_ARTIFACTS_DIR, "model.pkl")
    vectorizer_path = os.path.join(_ARTIFACTS_DIR, "vectorizer.pkl")

    if os.path.exists(model_path) and os.path.exists(vectorizer_path):
        _model = joblib.load(model_path)
        _vectorizer = joblib.load(vectorizer_path)
        logger.info("ML model loaded successfully.")
    else:
        logger.warning("Model artifacts not found. Run 'python -m app.ml.train_model' first.")
        logger.warning(f"Expected at: {_ARTIFACTS_DIR}")


# Load on import
_load_artifacts()


def predict_email(subject: str, body: str, sender: str) -> dict:
    """
    Predict phishing risk for a single email.

    Returns:
        {
            "risk_score": int (0-100),
            "label": str ("legitimate" | "suspicious" | "phishing"),
            "flagged_reasons": list[str],
            "suspicious_keywords": list[str],
        }
    """
    # If model not loaded, fall back to heuristic-only
    if _model is None or _vectorizer is None:
        return _heuristic_prediction(subject, body, sender)

    full_text = f"{subject} {body}"
    cleaned = clean_text(full_text)

    # TF-IDF features
    tfidf_vec = _vectorizer.transform([cleaned])

    # Extract suspicious keywords present in this specific email
    suspicious_keywords = []
    try:
        feature_names = _vectorizer.get_feature_names_out()
        non_zero_indices = tfidf_vec.nonzero()[1]
        coefs = _model.coef_[0]
        word_scores = []
        for idx in non_zero_indices:
            weight = coefs[idx]
            if weight > 0.5:
                word_scores.append((feature_names[idx], weight))
        word_scores.sort(key=lambda x: x[1], reverse=True)
        suspicious_keywords = [w[0] for w in word_scores[:7]]
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")

    # Handcrafted features (7 features matching trained model)
    urls = extract_urls(full_text)
    url_analysis = analyze_urls(urls)
    urgency_count, urgency_found = count_urgency_keywords(full_text)
    caps = calc_caps_ratio(full_text)
    punct = calc_punctuation_ratio(full_text)
    handcrafted = np.array([extract_handcrafted_features(full_text)])

    # Combined feature matrix (10000 TF-IDF + 7 Handcrafted = 10007)
    X = hstack([tfidf_vec, csr_matrix(handcrafted)])

    ml_score = None
    try:
        if hasattr(_model, "predict_proba"):
            proba = _model.predict_proba(X)[0]
            phishing_prob = proba[1] if len(proba) > 1 else proba[0]
            ml_score = int(round(phishing_prob * 100))
    except Exception as e:
        logger.warning(f"ML prediction failed, falling back to heuristic: {e}")

    if ml_score is None:
        return _heuristic_prediction(subject, body, sender)

    # ---------------------------------------------------------------------------
    # Heuristic scoring — calibrated to avoid false-positives on legitimate email
    # ---------------------------------------------------------------------------
    heuristic_score = 0

    # Only count SUSPICIOUS urls (IP-based, unknown domains) — not trusted CDN links
    suspicious_url_count = len(url_analysis["suspicious"])
    heuristic_score += min(suspicious_url_count * 12, 30)

    # Only count HIGH-CONFIDENCE urgency phrases specific to phishing
    heuristic_score += min(urgency_count * 10, 25)

    # Caps — penalise extreme cases (>35% caps is abnormal for real email)
    if caps > 0.35:
        heuristic_score += int(caps * 40)
    elif caps > 0.20:
        heuristic_score += 10

    # Subject line all uppercase
    if subject == subject.upper() and len(subject) > 6 and any(c.isalpha() for c in subject):
        heuristic_score += 15

    # Excessive punctuation — threshold tuned so ordinary conversational "!"
    # and "?" usage does not score points
    if punct > 0.03:
        heuristic_score += int(punct * 300)

    # Suspicious sender
    suspicious, _ = is_sender_suspicious(sender)
    if suspicious:
        heuristic_score += 20

    # Brand impersonation (display-name spoofing / fake brand link domains / subject spoofing)
    impersonation_issues = detect_brand_impersonation(sender, urls, subject)
    if impersonation_issues:
        heuristic_score += min(len(impersonation_issues) * 25, 45)

    # ---------------------------------------------------------------------------
    # Blend: 60% ML, 40% Heuristic
    # ---------------------------------------------------------------------------
    risk_score = int(0.6 * ml_score + 0.4 * heuristic_score)

    # Trusted sender bonus — legitimate business emails from verified corporate
    # domains. Free personal providers (gmail.com etc.) do NOT qualify: anyone
    # can open such an account. Suppressed entirely on impersonation detection.
    if is_sender_trusted(sender) and not is_free_mail_sender(sender) and not impersonation_issues:
        risk_score = max(0, risk_score - 25)

    # Clamp to 0–100
    risk_score = max(0, min(100, risk_score))

    # Corroboration guard — when a very short email carries ZERO supporting
    # heuristic evidence (no links, no urgency phrases, clean style), the ML
    # score alone must never push it into suspicious/phishing.
    if heuristic_score == 0 and len(full_text.split()) < 80:
        risk_score = min(risk_score, 34)

    # Determine label with updated thresholds
    label = _score_to_label(risk_score)

    # Generate explanations
    flagged_reasons = _generate_reasons(
        subject, body, sender, urls, url_analysis,
        urgency_count, urgency_found, caps, punct, risk_score
    )

    return {
        "risk_score": risk_score,
        "label": label,
        "flagged_reasons": flagged_reasons,
        "suspicious_keywords": suspicious_keywords,
    }


def _score_to_label(score: int) -> str:
    """
    Convert numeric risk score to a label.
    """
    if score <= 35:
        return "legitimate"
    elif score <= 65:
        return "suspicious"
    else:
        return "phishing"


def _generate_reasons(
    subject, body, sender, urls, url_analysis,
    urgency_count, urgency_found, caps, punct, risk_score
) -> list:
    """
    Generate human-readable explanations. Only shows reasons that actually fired.
    """
    reasons = []

    # Brand impersonation issues
    impersonation_issues = detect_brand_impersonation(sender, urls, subject)

    # Trusted sender note
    if is_sender_trusted(sender) and not is_free_mail_sender(sender) and not impersonation_issues:
        reasons.append("✓ Sender domain is verified and trusted")

    # URL analysis
    suspicious_urls = url_analysis.get("suspicious", [])
    clean_urls = url_analysis.get("clean", [])

    if clean_urls:
        reasons.append(f"✓ {len(clean_urls)} link(s) from verified domains detected")
    if suspicious_urls:
        reasons.append(f"⚠ {len(suspicious_urls)} link(s) from unverified/unknown domains")
        for url in suspicious_urls[:2]:
            reasons.append(f"  → Unverified URL: {url[:70]}{'...' if len(url) > 70 else ''}")

    # High-confidence urgency keywords
    if urgency_count > 0:
        kw_list = ", ".join(f"'{kw}'" for kw in urgency_found[:3])
        reasons.append(f"⚠ Contains high-risk urgency phrase(s): {kw_list}")

    # Extreme caps usage
    if caps > 0.35:
        reasons.append(f"⚠ Abnormally high uppercase text ({int(caps * 100)}%) — unusual for legitimate email")
    elif caps > 0.20:
        reasons.append(f"Moderate uppercase usage ({int(caps * 100)}%)")

    # Punctuation abuse
    if punct > 0.035:
        reasons.append(f"⚠ Excessive exclamation/question marks (ratio: {punct:.3f})")

    # Sender analysis
    suspicious, sender_reason = is_sender_suspicious(sender)
    if suspicious:
        reasons.append(f"⚠ Suspicious sender: {sender_reason}")

    # Brand impersonation issues
    for issue in impersonation_issues:
        reasons.append(f"⚠ {issue}")

    # Subject line analysis
    if subject == subject.upper() and len(subject) > 5 and any(c.isalpha() for c in subject):
        reasons.append("⚠ Subject line is entirely in UPPERCASE")

    # Request for personal info
    body_lower = body.lower()
    personal_info_keywords = [
        "bank account number", "credit card number", "cvv",
        "social security number", "ssn", "date of birth",
        "provide your password", "confirm your password",
    ]
    found_pii = [kw for kw in personal_info_keywords if kw in body_lower]
    if found_pii:
        reasons.append(f"⚠ Explicitly requests sensitive personal information: {', '.join(found_pii)}")

    # Threat/consequence language
    threat_keywords = [
        "account will be disabled", "account will be locked",
        "account will be suspended", "permanently deleted",
        "cannot be reversed", "account will be frozen"
    ]
    found_threats = [kw for kw in threat_keywords if kw in body_lower]
    if found_threats:
        reasons.append(f"⚠ Contains threat/consequence language: '{found_threats[0]}'")

    # If no specific reasons found
    if not reasons:
        if risk_score <= 35:
            reasons.append("✓ No suspicious indicators detected — email appears legitimate")
        else:
            reasons.append("ML model detected subtle patterns associated with phishing")

    return reasons


def _heuristic_prediction(subject: str, body: str, sender: str) -> dict:
    """Fallback when ML model is not loaded — uses only handcrafted features."""
    full_text = f"{subject} {body}"
    urls = extract_urls(full_text)
    url_analysis = analyze_urls(urls)
    urgency_count, urgency_found = count_urgency_keywords(full_text)
    caps = calc_caps_ratio(full_text)
    punct = calc_punctuation_ratio(full_text)
    suspicious, sender_reason = is_sender_suspicious(sender)
    trusted = is_sender_trusted(sender)
    free_mail = is_free_mail_sender(sender)

    score = 0
    score += min(len(url_analysis["suspicious"]) * 12, 30)
    score += min(urgency_count * 10, 25)
    score += int(caps * 40) if caps > 0.35 else (10 if caps > 0.20 else 0)
    if subject == subject.upper() and len(subject) > 6 and any(c.isalpha() for c in subject):
        score += 15
    score += int(punct * 300) if punct > 0.03 else 0
    score += 20 if suspicious else 0
    impersonation_issues = detect_brand_impersonation(sender, urls, subject)
    score += min(len(impersonation_issues) * 25, 45)
    if trusted and not free_mail and not impersonation_issues:
        score = max(0, score - 25)

    score = max(0, min(100, score))
    label = _score_to_label(score)

    reasons = _generate_reasons(
        subject, body, sender, urls, url_analysis,
        urgency_count, urgency_found, caps, punct, score
    )

    return {
        "risk_score": score,
        "label": label,
        "flagged_reasons": reasons,
        "suspicious_keywords": [],
    }

