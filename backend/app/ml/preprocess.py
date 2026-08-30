"""
preprocess.py — Email text cleaning and feature extraction.
Includes trusted domain allowlist and accurate sender heuristics.
"""

import re
from bs4 import BeautifulSoup
import nltk
from nltk.stem import WordNetLemmatizer

# Ensure wordnet is downloaded gracefully
try:
    nltk.data.find('corpora/wordnet.zip')
except LookupError:
    nltk.download('wordnet', quiet=True)

lemmatizer = WordNetLemmatizer()


URGENCY_KEYWORDS = [
    "verify your account now",
    "verify your account",
    "verify your identity",
    "account will be locked",
    "account will be suspended",
    "account has been suspended",
    "account has been compromised",
    "account has been restricted",
    "account is suspended",
    "account suspended",
    "confirm your identity immediately",
    "confirm your identity",
    "unauthorized access detected",
    "unauthorized access",
    "detected unauthorized access",
    "unauthorized activity",
    "your account has been compromised",
    "failure to verify will result",
    "respond within 24 hours or",
    "respond within 24 hours",
    "within 24 hours",
    "claim your prize",
    "you've been selected as winner",
    "you have won",
    "you won",
    "you've won",
    "congrats",
    "congratulations",
    "redeem your",
    "gift voucher",
    "cash prize",
    "lucky draw",
    "wire transfer required",
    "send your bank details",
    "provide your ssn",
    "provide your social security",
    "click here to avoid suspension",
    "click here to verify",
    "your account is at risk",
    "verify immediately to avoid",
    "verify immediately",
    "act now or lose access",
    "act immediately",
    "immediate action required",
    "urgent action required",
    "final notice",
    "last warning",
    "secure your funds",
    "restore your account",
]


def extract_handcrafted_features(text: str) -> list:
    """
    Extract numeric handcrafted features from raw email text (7 features).
    Must match exactly between training and prediction.
    """
    import numpy as np
    urls = extract_urls(text)
    urgency_count, _ = count_urgency_keywords(text)
    caps = calc_caps_ratio(text)
    punct = calc_punctuation_ratio(text)

    text_length = float(np.log1p(len(text)))
    word_count = max(len(text.split()), 1)
    link_to_text_ratio = float(len(urls) / word_count * 100)
    has_html = 1.0 if ("<a " in text.lower() or "<img" in text.lower()
                        or "<table" in text.lower() or "<div" in text.lower()
                        or "<html" in text.lower()) else 0.0

    return [len(urls), urgency_count, caps, punct,
            text_length, link_to_text_ratio, has_html]


# ---------------------------------------------------------------------------
# Trusted top-level domains — emails FROM these are likely legitimate
# ---------------------------------------------------------------------------
TRUSTED_DOMAINS = {
    # Google / Alphabet
    "google.com", "gmail.com", "googlemail.com", "googleapis.com",
    "accounts.google.com", "mail.google.com", "youtube.com",
    "google.co.in", "google.co.uk",
    # Microsoft
    "microsoft.com", "outlook.com", "hotmail.com", "live.com",
    "office.com", "office365.com", "azure.com", "linkedin.com",
    "microsoftonline.com",
    # Amazon / AWS
    "amazon.com", "amazon.in", "amazon.co.uk", "amazonaws.com",
    "aws.amazon.com",
    # Apple
    "apple.com", "icloud.com", "me.com",
    # Social
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "reddit.com", "pinterest.com", "tiktok.com",
    # Finance / Banking (major ones)
    "paypal.com", "stripe.com", "razorpay.com", "paytm.com",
    # Communication
    "zoom.us", "slack.com", "discord.com", "whatsapp.com",
    "telegram.org", "teams.microsoft.com",
    # Dev / Infra
    "github.com", "gitlab.com", "stackoverflow.com", "atlassian.com",
    "jira.atlassian.com", "bitbucket.org", "heroku.com",
    "netlify.com", "vercel.com", "cloudflare.com", "digitalocean.com",
    # Education
    "coursera.org", "udemy.com", "edx.org", "khanacademy.org",
    # Shopping / E-commerce
    "flipkart.com", "myntra.com", "snapdeal.com", "ebay.com",
    "shopify.com", "etsy.com",
    # Food / Services
    "swiggy.com", "zomato.com", "uber.com", "ola.com",
    # Utilities
    "noreply.github.com", "notifications.github.com",
}

# Suspicious TLD/domain patterns (must be complete domain, not substring)
SUSPICIOUS_DOMAIN_PATTERNS = [
    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",   # Raw IP address
    r"^.*-verify-account\.",                       # -verify-account.anything
    r"^.*-secure-login\.",
    r"^.*-account-alert\.",
    r"^.*\.tk$",                                   # Free TLDs commonly used in phishing
    r"^.*\.ml$",
    r"^.*\.ga$",
    r"^.*\.cf$",
    r"^.*\.gq$",
]

# Number-letter substitution patterns that indicate typosquatting
# Only apply to local part of email or clear brand lookalikes
TYPOSQUAT_BRANDS = {
    "paypa1": "paypal",
    "paypai": "paypal",
    "amaz0n": "amazon",
    "arnazon": "amazon",
    "g00gle": "google",
    "googIe": "google",  # capital I instead of l
    "micros0ft": "microsoft",
    "app1e": "apple",
    "netfl1x": "netflix",
    "faceb00k": "facebook",
}


def clean_text(text: str) -> str:
    """Clean email text: strip HTML, lowercase, remove extra whitespace."""
    if not isinstance(text, str) or not text:
        return ""
    # Strip HTML tags
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ")
    # Lowercase
    text = text.lower()

    # Lemmatization for better TF-IDF features
    words = re.findall(r'\b[a-z]+\b', text)
    lemmatized_words = [lemmatizer.lemmatize(word) for word in words]
    text = " ".join(lemmatized_words)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_urls(text: str) -> list:
    """Extract all URLs from text."""
    # NOTE: the closing ']' must be escaped inside the class, otherwise the
    # class terminates early and plain URLs (no trailing ']') never match.
    url_pattern = r"https?://[^\s<>\"'()\[\]\\]+"
    return [u.rstrip(".,;:!?") for u in re.findall(url_pattern, text, re.IGNORECASE)]


def count_urgency_keywords(text: str) -> tuple:
    """
    Count HIGH-CONFIDENCE urgency keywords found only in phishing.
    Returns (count, list_of_found_keywords).
    """
    text_lower = text.lower()
    found = []
    for kw in URGENCY_KEYWORDS:
        if kw in text_lower:
            found.append(kw)
    return len(found), found


def calc_caps_ratio(text: str) -> float:
    """Calculate the ratio of uppercase characters to total alphabetic chars."""
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return 0.0
    upper = sum(1 for c in alpha_chars if c.isupper())
    return round(upper / len(alpha_chars), 3)


def calc_punctuation_ratio(text: str) -> float:
    """Calculate ratio of exclamation/question marks to total characters."""
    if not text:
        return 0.0
    excessive = sum(1 for c in text if c in "!?")
    return round(excessive / len(text), 4)


def get_sender_domain(sender: str) -> str | None:
    """Extract the root domain from a sender string."""
    if not sender:
        return None
    match = re.search(r"@([\w.-]+)", sender)
    if not match:
        return None
    return match.group(1).lower()


def is_sender_trusted(sender: str) -> bool:
    """
    Returns True if the sender's domain is in the trusted allowlist.
    Handles subdomains: e.g., 'notifications.github.com' → trusted via 'github.com'.
    """
    domain = get_sender_domain(sender)
    if not domain:
        return False

    # Direct match
    if domain in TRUSTED_DOMAINS:
        return True

    # Subdomain match: check if the base domain (last 2 parts) is trusted
    parts = domain.split(".")
    if len(parts) >= 2:
        base = ".".join(parts[-2:])
        if base in TRUSTED_DOMAINS:
            return True

    return False


def is_sender_suspicious(sender: str) -> tuple:
    """
    Check if sender domain looks suspicious. Returns (bool, reason).

    FIXED: Previously matched any digit in the full domain (e.g., 365.microsoft.com
    has '3' and would be flagged). Now only checks the LOCAL PART of the email
    for typosquatting, and matches against known brand lookalikes.

    NOTE: is_sender_trusted is NOT checked here first — free providers like gmail.com
    are trusted for real addresses, but we still need to flag gmail.com if someone
    uses it to impersonate an official service (e.g. paypal-support@gmail.com).
    """
    if not sender:
        return False, ""

    domain = get_sender_domain(sender)
    if not domain:
        return False, ""

    # Extract local part (before @)
    local_match = re.match(r"([^@]+)@", sender)
    local_part = local_match.group(1).lower() if local_match else ""

    # Free provider impersonating an official service — check BEFORE trusted-domain skip
    free_providers = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com"]
    official_keywords = ["bank", "paypal", "amazon", "apple", "microsoft",
                         "netflix", "security", "admin", "support", "account",
                         "billing", "payment", "helpdesk", "noreply"]

    if domain in free_providers:
        for kw in official_keywords:
            if kw in local_part:
                return True, f"Official-sounding name '{local_part}' sent from personal email '{domain}'"

    # If sender is in trusted allowlist — not suspicious
    if is_sender_trusted(sender):
        return False, ""

    # Check for known typosquatting patterns in the LOCAL PART or domain
    for fake, real in TYPOSQUAT_BRANDS.items():
        if fake in local_part or fake in domain:
            return True, f"Domain/address '{domain}' appears to spoof '{real}'"

    # Check suspicious domain patterns (full domain regex)
    for pattern in SUSPICIOUS_DOMAIN_PATTERNS:
        if re.match(pattern, domain):
            return True, f"Domain '{domain}' matches a suspicious pattern"

    return False, ""


def analyze_urls(urls: list) -> dict:
    """
    Analyze URLs for suspicious indicators.
    Returns a breakdown of suspicious vs. clean URLs.
    """
    suspicious_urls = []
    clean_urls = []

    for url in urls:
        # Extract domain from URL
        domain_match = re.search(r"https?://([^/?\s]+)", url)
        if not domain_match:
            suspicious_urls.append(url)
            continue

        url_domain = domain_match.group(1).lower().lstrip("www.")

        # Check if URL domain is trusted
        parts = url_domain.split(".")
        base = ".".join(parts[-2:]) if len(parts) >= 2 else url_domain
        if url_domain in TRUSTED_DOMAINS or base in TRUSTED_DOMAINS:
            clean_urls.append(url)
        elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", url_domain):
            suspicious_urls.append(url)  # IP-based URL
        elif any(re.match(p, url_domain) for p in SUSPICIOUS_DOMAIN_PATTERNS):
            suspicious_urls.append(url)
        else:
            # Unknown domain — mildly suspicious but not certain
            suspicious_urls.append(url)

    return {
        "suspicious": suspicious_urls,
        "clean": clean_urls,
    }


# ---------------------------------------------------------------------------
# Brand impersonation detection — catches spoofing that text ML alone misses:
#   1. Display name claims a brand but sender domain doesn't belong to it
#      e.g. "Microsoft Security" <random96@gmail.com>
#   2. Link domains contain a brand token but point elsewhere
#      e.g. https://secure-paypal-login.ru/verify
# ---------------------------------------------------------------------------
BRAND_OFFICIAL_DOMAINS = {
    "paypal": "paypal.com",
    "apple": "apple.com",
    "icloud": "icloud.com",
    "microsoft": "microsoft.com",
    "outlook": "outlook.com",
    "google": "google.com",
    "gmail": "gmail.com",
    "amazon": "amazon.com",
    "netflix": "netflix.com",
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "whatsapp": "whatsapp.com",
    "linkedin": "linkedin.com",
    "hdfc": "hdfcbank.com",
    "sbi": "sbi.co.in",
    "icici": "icicibank.com",
    "kotak": "kotak.com",
    "paytm": "paytm.com",
    "phonepe": "phonepe.com",
    "binance": "binance.com",
    "coinbase": "coinbase.com",
    "dhl": "dhl.com",
    "fedex": "fedex.com",
}

# Brands whose official mail legitimately arrives from several related bases
ACCEPTABLE_SENDER_BASES = {
    "gmail.com": {"gmail.com", "googlemail.com", "google.com"},
    "google.com": {"google.com", "googlemail.com", "gmail.com"},
}


def _acceptable_bases_for(brand: str, official: str) -> set:
    """A brand may legitimately send from its official domain plus any trusted
    sibling domain sharing its first label (amazon.in for amazon, etc.)."""
    bases = {official} | set(ACCEPTABLE_SENDER_BASES.get(official, set()))
    bases |= {d for d in TRUSTED_DOMAINS if d.split(".")[0] == brand}
    return bases


# Pre-computed once at import time for fast lookups
_BRAND_ACCEPTABLE_BASES = {
    brand: _acceptable_bases_for(brand, official)
    for brand, official in BRAND_OFFICIAL_DOMAINS.items()
}


# Free/personal mailbox providers — anyone can create these accounts, so they
# must NOT receive the verified-sender trust discount (corporate domains like
# google.com or amazon.com still do).
FREE_MAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "protonmail.com", "proton.me", "rediffmail.com",
}


def is_free_mail_sender(sender: str) -> bool:
    """True when the sender address belongs to a free personal mailbox provider."""
    domain = get_sender_domain(sender)
    if not domain:
        return False
    if domain in FREE_MAIL_PROVIDERS:
        return True
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:]) in FREE_MAIL_PROVIDERS
    return False


def get_display_name(sender: str) -> str:
    """Extract the display name from '"PayPal Support" <a@b.com>' style senders."""
    if not sender:
        return ""
    match = re.match(r'^"?([^"<]+?)"?\s*<', sender.strip())
    return match.group(1).strip() if match else ""


def _base_domain_of(host: str | None) -> str | None:
    """Reduce a host to its registrable base domain (last two labels)."""
    if not host:
        return None
    parts = host.lower().lstrip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def detect_brand_impersonation(sender: str, urls: list, subject: str = "") -> list:
    """
    Return a list of human-readable brand-impersonation issues for an email.
    Tokens are matched on hyphen/dot boundaries so 'backup-cdn.com' does NOT
    trigger the 'ups' brand, while 'secure-paypal-login.ru' DOES trigger paypal.
    Also detects when the subject line claims a brand account/security action
    while sending from a personal or non-official domain.
    """
    issues: list[str] = []
    sender_domain = get_sender_domain(sender)
    sender_base = _base_domain_of(sender_domain)

    # 1) Display-name spoofing: "Brand X" from a domain that isn't Brand X's
    display_name = get_display_name(sender).lower()
    if display_name and sender_base:
        for brand, official in BRAND_OFFICIAL_DOMAINS.items():
            if re.search(rf"\b{brand}\b", display_name):
                if sender_base not in _BRAND_ACCEPTABLE_BASES[brand]:
                    issues.append(
                        f"Display name claims '{brand.title()}' "
                        f"but mail comes from '{sender_domain}'"
                    )
                break

    # 2) Subject line brand spoofing: e.g. "Urgent: Your PayPal Account Has Been Suspended" from gmail
    subject_lower = (subject or "").lower()
    if subject_lower and sender_base:
        security_terms = ["account", "suspended", "locked", "security", "unauthorized", "alert", "verify", "compromised", "funds", "billing", "payment"]
        for brand, official in BRAND_OFFICIAL_DOMAINS.items():
            if re.search(rf"\b{brand}\b", subject_lower):
                if sender_base not in _BRAND_ACCEPTABLE_BASES[brand]:
                    if any(st in subject_lower for st in security_terms):
                        issues.append(
                            f"Subject mentions '{brand.title()}' account alert but sent from unofficial domain '{sender_domain}'"
                        )
                        break

    # 3) URL domains impersonating brands they don't belong to
    seen = set()
    for url in urls or []:
        match = re.match(r"https?://([^/?\s]+)", url, re.IGNORECASE)
        if not match:
            continue
        host = match.group(1).lower()
        base_host = _base_domain_of(host)
        # Skip trusted link targets and links back to the sender's own domain
        if (base_host in TRUSTED_DOMAINS or base_host == sender_base):
            continue
        tokens = re.split(r"[-.]", host)
        for brand, official in BRAND_OFFICIAL_DOMAINS.items():
            if brand in tokens and base_host != official:
                if base_host in _BRAND_ACCEPTABLE_BASES[brand]:
                    continue
                key = (brand, base_host)
                if key not in seen:
                    seen.add(key)
                    issues.append(
                        f"Link domain '{base_host}' impersonates "
                        f"'{brand.title()}' (official: {official})"
                    )
                break

    return issues[:4]



def extract_features(subject: str, body: str, sender: str) -> dict:
    """
    Extract all features from an email for ML prediction.
    Returns a dict with both numeric features and metadata for explanations.
    """
    full_text = f"{subject} {body}"
    cleaned = clean_text(full_text)

    # URL features
    urls = extract_urls(full_text)
    url_analysis = analyze_urls(urls)

    # Urgency features
    urgency_count, urgency_found = count_urgency_keywords(full_text)

    # Text style features
    caps_ratio = calc_caps_ratio(full_text)
    punct_ratio = calc_punctuation_ratio(full_text)

    # Sender analysis
    sender_suspicious, sender_reason = is_sender_suspicious(sender)
    sender_trusted = is_sender_trusted(sender)

    return {
        "cleaned_text": cleaned,
        "url_count": len(urls),
        "suspicious_url_count": len(url_analysis["suspicious"]),
        "clean_url_count": len(url_analysis["clean"]),
        "urls_found": urls,
        "suspicious_urls": url_analysis["suspicious"],
        "urgency_count": urgency_count,
        "urgency_keywords_found": urgency_found,
        "caps_ratio": caps_ratio,
        "punctuation_ratio": punct_ratio,
        "sender_suspicious": 1 if sender_suspicious else 0,
        "sender_trusted": 1 if sender_trusted else 0,
        "sender_reason": sender_reason,
    }
