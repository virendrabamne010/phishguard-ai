"""
generate_dataset.py — Multi-source phishing/spam dataset builder.

Combines four sources for a balanced, diverse training set:
  1. Enron Spam Corpus        (SetFit/enron_spam)          — spam vs ham baseline
  2. Nazario Phishing Corpus  (ealvaradob/phishing-dataset) — real phishing emails
  3. SpamAssassin Corpus      (talby/spamassassin)         — classic benchmark
  4. Curated Phishing Templates                             — modern attack patterns

Total target: ~50,000 balanced samples (phishing=1, legitimate=0).
"""

import os
import csv
import random
import hashlib

# ---------------------------------------------------------------------------
# Curated modern phishing templates — patterns the academic corpora miss
# ---------------------------------------------------------------------------
MODERN_PHISHING_TEMPLATES = [
    # Crypto scams
    "Urgent: Your Binance account has been flagged for suspicious activity. Verify your identity immediately at https://binance-secure-verify.com/auth or your account will be permanently locked within 24 hours.",
    "Congratulations! You've been selected for our exclusive Bitcoin airdrop. Claim your 0.5 BTC now at https://crypto-reward-claim.net before the offer expires. Limited time only!",
    "Your Coinbase wallet has been compromised. Reset your password immediately at https://coinbase-security-alert.com/reset to prevent unauthorized transactions.",
    "ALERT: Unusual login attempt detected on your MetaMask wallet. Secure your assets now at https://metamask-verify.io/secure or risk losing your funds.",
    "Your crypto portfolio has earned $5,000 in rewards! Withdraw now at https://defi-rewards-portal.com/withdraw. Offer valid for 48 hours only.",

    # 2FA / MFA bypass
    "Microsoft Security Alert: We detected a sign-in from an unrecognized device. Verify your identity by entering your verification code at https://microsoft-security-verify.com/2fa",
    "Your Google 2-Step Verification needs to be updated. Click here to re-authenticate: https://google-auth-update.com/verify. Failure to update within 12 hours will result in account suspension.",
    "Apple ID: Your two-factor authentication has expired. Re-enable it now at https://apple-id-security.net/2fa to maintain account access.",

    # Package / delivery scams
    "Your DHL package #DHL-7284903 could not be delivered due to an incorrect address. Update your shipping information at https://dhl-delivery-update.com/track to reschedule delivery.",
    "FedEx Notification: Your package is being held at customs. Pay the $3.99 clearance fee at https://fedex-customs-pay.com/clear to release your package.",
    "Amazon Delivery Update: Your order #AMZ-9284756 has been delayed. Confirm your address at https://amazon-delivery-confirm.net/update to ensure timely delivery.",
    "USPS: Your package requires additional verification. Click https://usps-verify-package.com/confirm to provide your details and receive your delivery.",
    "Royal Mail: We attempted delivery of your parcel but no one was available. Reschedule at https://royalmail-redelivery.com/book by paying the £1.50 re-delivery fee.",

    # Bank / financial phishing
    "HDFC Bank Alert: Suspicious transaction detected on your account ending in XXXX. Verify your identity at https://hdfc-secure-banking.com/verify immediately.",
    "Your SBI NetBanking access has been temporarily suspended due to unusual activity. Reactivate at https://sbi-netbanking-verify.com/reactivate.",
    "ICICI Bank: Your KYC documents have expired. Update your KYC at https://icici-kyc-update.com/upload to avoid account freeze.",
    "PayPal: We noticed unauthorized activity on your account. Secure your account now at https://paypal-resolution-center.net/secure.",
    "Chase Bank: Your online banking session has expired. Re-login at https://chase-online-banking.com/login to continue managing your account.",
    "Wells Fargo Security: Your account has been limited. Please restore your account by visiting https://wellsfargo-account-restore.com/verify.",
    "Bank of America: We detected unusual spending patterns. Review your recent transactions at https://bofa-fraud-alert.com/review.",

    # Social media phishing
    "Instagram: Your account has been reported for violating community guidelines. Appeal the decision at https://instagram-appeal-center.com/review or your account will be deleted in 24 hours.",
    "Facebook Security: Someone tried to log in to your account from Russia. Secure your account at https://facebook-security-center.net/lock.",
    "LinkedIn: You have 3 new job offers waiting. View them at https://linkedin-job-offers.com/view before they expire.",
    "Twitter/X: Your account has been flagged for suspicious activity. Verify at https://x-account-verify.com/auth.",
    "TikTok Creator Fund: You've earned $500 in creator rewards! Claim at https://tiktok-creator-payout.com/claim.",

    # Tech support scams
    "Windows Defender Alert: Your PC is infected with 3 critical viruses! Call our support team at 1-800-555-0199 or visit https://microsoft-support-help.com/fix immediately.",
    "Norton Security: Your antivirus subscription has expired. Renew now at https://norton-renewal-center.com/renew to stay protected. Your system is currently vulnerable!",
    "McAfee: URGENT - Your device is at risk! 28 threats detected. Renew your protection at https://mcafee-threat-alert.com/protect.",

    # Tax / government scams
    "IRS Notice: You have an outstanding tax refund of $3,847.00. Claim your refund at https://irs-tax-refund.com/claim by providing your SSN and bank details.",
    "HMRC: You are eligible for a tax rebate of £742.00. Submit your claim at https://hmrc-rebate-portal.com/claim within 7 days.",
    "Social Security Administration: Your SSN has been suspended due to suspicious activity. Call immediately at 1-800-555-0177 to reactivate.",

    # Prize / lottery scams
    "You've won a $1,000,000 prize in the International Lottery! To claim your winnings, send your full name, address, and bank details to claims@intl-lottery-winners.com.",
    "Congratulations! Your email was randomly selected for our Microsoft Annual Sweepstakes. You've won $500,000! Claim at https://microsoft-sweepstakes.net/claim.",
    "iPhone 15 Pro Giveaway! You've been selected as one of 100 winners! Claim your free iPhone at https://apple-giveaway-2024.com/claim.",

    # Cloud service phishing
    "Dropbox: Someone shared a document with you. View it at https://dropbox-shared-docs.com/view?id=8472.",
    "Google Drive: An important document requires your immediate attention. Open at https://google-drive-docs.net/view.",
    "OneDrive: Your storage is 95% full. Upgrade your plan at https://onedrive-upgrade-storage.com/upgrade for free 1TB bonus storage.",
    "DocuSign: You have a document pending your signature. Review and sign at https://docusign-review-docs.com/sign.",

    # HR / corporate phishing
    "HR Department: Your direct deposit information needs to be updated. Please fill out the form at https://hr-payroll-update.com/form before the next pay cycle.",
    "IT Department: Your email password expires today. Reset it now at https://company-password-reset.com/update to avoid losing access.",
    "CEO Request: I need you to purchase gift cards for a client meeting urgently. Please buy 5x $100 Amazon gift cards and email me the codes. This is confidential.",
    "Urgent: Please review the attached invoice #INV-2024-0847 and process payment immediately. Wire transfer details at https://invoice-payment-portal.com/pay.",

    # Subscription phishing
    "Netflix: Your subscription payment has failed. Update your billing information at https://netflix-billing-update.com/payment to avoid service interruption.",
    "Spotify: Your Premium subscription will be cancelled in 24 hours. Confirm your payment method at https://spotify-premium-billing.com/confirm.",
    "Disney+: Action Required - Your payment method has been declined. Update at https://disneyplus-billing.com/update.",
    "HBO Max: Your account will be deactivated due to payment failure. Reactivate at https://hbomax-reactivate.com/billing.",

    # COVID / health scams
    "WHO Alert: New COVID variant detected in your area. Register for priority vaccination at https://who-vaccine-register.com/signup. Limited slots available.",
    "Health Department: Your COVID test results are ready. View at https://covid-results-portal.com/view by entering your SSN for verification.",

    # Charity / donation scams
    "Red Cross Emergency Appeal: Devastating earthquake victims need your help! Donate now at https://redcross-emergency-fund.net/donate.",
    "UNICEF: Help children in need this holiday season. Every $1 you donate feeds a child for a week. Donate at https://unicef-holiday-giving.com/donate.",

    # Advanced phishing with urgency
    "FINAL WARNING: Your email account will be permanently deleted in 2 hours due to inactivity. Verify ownership at https://email-verify-urgent.com/keep to save your account and all data.",
    "Security Notice: Multiple failed login attempts detected on your account. Your account has been temporarily locked. Unlock at https://account-unlock-now.com/verify within 1 hour.",
    "System Administrator: Your mailbox has exceeded its storage quota. Delete messages or expand your storage at https://mail-quota-expand.com/upgrade to continue receiving emails.",
]

# Curated legitimate email templates for balance
MODERN_LEGITIMATE_TEMPLATES = [
    "Hi team, please find the meeting notes attached from today's standup. Let me know if there are any action items I missed. Thanks!",
    "Just wanted to follow up on our conversation from last week. Have you had a chance to review the proposal? No rush, just checking in.",
    "Hey! Are we still on for dinner this Friday? I was thinking we could try that new Italian place downtown. Let me know!",
    "Reminder: Your appointment with Dr. Smith is scheduled for Tuesday, March 15th at 2:30 PM. Please arrive 10 minutes early.",
    "Thank you for your order #ORD-284756. Your items have been shipped and should arrive within 3-5 business days. Track your order at amazon.com/orders.",
    "Welcome to our monthly newsletter! Here are the top stories from this week. Read more on our blog at company.com/blog.",
    "Your electricity bill for March is $127.45. Payment is due by April 15th. You can pay online at your utility provider's website.",
    "Happy Birthday! Wishing you a wonderful year ahead. Hope you have a great celebration!",
    "The project deadline has been extended to next Friday. Please make sure to submit your final deliverables by end of day.",
    "Great news! Your loan application has been approved. Please visit your nearest branch to complete the paperwork.",
    "Hi, I'm writing to confirm our meeting scheduled for tomorrow at 10 AM. Please let me know if the conference room is available.",
    "Your flight reservation has been confirmed. Departure: March 20, 8:30 AM from JFK. Arrive 2 hours before departure time.",
    "Thank you for attending our webinar on Cloud Security. Here are the slides and recording link for your reference.",
    "Please review the attached quarterly report and share your feedback by Friday. Looking forward to your insights.",
    "Your subscription renewal was successful. Your next billing date is April 1st. No action needed on your part.",
    "Hi there! Just a quick update — we've pushed the new feature to staging. Could you please test it when you get a chance?",
    "Thanks for reaching out to our support team. We've received your ticket #SUP-4829 and will get back to you within 24 hours.",
    "Your package has been delivered! It was left at your front door at 2:15 PM today. Thank you for shopping with us.",
    "Congratulations on completing the course! Your certificate of completion is now available for download in your account.",
    "Weekly digest: Here's a summary of the 12 pull requests merged this week. Great work, team!",
]


def generate_dataset(output_path: str, total_rows: int = 50000):
    """
    Fetch and combine multiple real-world phishing/spam datasets into one
    balanced CSV.  Falls back gracefully when a HuggingFace dataset is
    temporarily unavailable.
    """
    from datasets import load_dataset

    all_phishing: list[str] = []
    all_legitimate: list[str] = []
    sources_used: list[str] = []

    # ------------------------------------------------------------------
    # Source 1: Enron Spam Corpus (SetFit/enron_spam)
    # ------------------------------------------------------------------
    try:
        print("[INFO] Downloading SetFit/enron_spam from HuggingFace...")
        ds = load_dataset("SetFit/enron_spam", split="train")
        for item in ds:
            text = (item.get("text") or "").strip()
            if len(text) < 20:
                continue
            if item["label"] == 1:
                all_phishing.append(text)
            else:
                all_legitimate.append(text)
        sources_used.append(f"enron_spam ({len(ds)} raw)")
        print(f"   [OK] Loaded {len(ds)} samples from Enron Spam")
    except Exception as e:
        print(f"   [X] Enron Spam unavailable: {e}")

    # ------------------------------------------------------------------
    # Source 2: Nazario Phishing Corpus (ealvaradob/phishing-dataset)
    # ------------------------------------------------------------------
    try:
        print("[INFO] Downloading ealvaradob/phishing-dataset from HuggingFace...")
        ds = load_dataset("ealvaradob/phishing-dataset", "combined", split="train", trust_remote_code=True)
        for item in ds:
            text = (item.get("text") or item.get("email_text") or "").strip()
            if len(text) < 20:
                continue
            label = item.get("label", -1)
            if label == 1:
                all_phishing.append(text)
            elif label == 0:
                all_legitimate.append(text)
        sources_used.append(f"nazario_phishing ({len(ds)} raw)")
        print(f"   [OK] Loaded {len(ds)} samples from Nazario Phishing")
    except Exception as e:
        print(f"   [X] Nazario Phishing unavailable: {e}")

    # ------------------------------------------------------------------
    # Source 3: SpamAssassin Corpus (talby/spamassassin)
    # ------------------------------------------------------------------
    try:
        print("[INFO] Downloading talby/spamassassin from HuggingFace...")
        ds = load_dataset("talby/spamassassin", split="train", trust_remote_code=True)
        for item in ds:
            text = (item.get("text") or item.get("email") or "").strip()
            if len(text) < 20:
                continue
            label = item.get("label", -1)
            if label == 1:
                all_phishing.append(text)
            elif label == 0:
                all_legitimate.append(text)
        sources_used.append(f"spamassassin ({len(ds)} raw)")
        print(f"   [OK] Loaded {len(ds)} samples from SpamAssassin")
    except Exception as e:
        print(f"   [X] SpamAssassin unavailable: {e}")

    # ------------------------------------------------------------------
    # Source 4: Curated Modern Phishing Templates
    # ------------------------------------------------------------------
    all_phishing.extend(MODERN_PHISHING_TEMPLATES)
    all_legitimate.extend(MODERN_LEGITIMATE_TEMPLATES)
    sources_used.append(f"curated_templates ({len(MODERN_PHISHING_TEMPLATES)} phish + {len(MODERN_LEGITIMATE_TEMPLATES)} legit)")
    print(f"   [OK] Added {len(MODERN_PHISHING_TEMPLATES)} curated phishing + {len(MODERN_LEGITIMATE_TEMPLATES)} legitimate templates")

    # ------------------------------------------------------------------
    # Deduplicate by content hash
    # ------------------------------------------------------------------
    def dedupe(texts: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for t in texts:
            h = hashlib.md5(t.encode("utf-8", errors="ignore")).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(t)
        return unique

    all_phishing = dedupe(all_phishing)
    all_legitimate = dedupe(all_legitimate)

    print(f"\n[INFO] After deduplication:")
    print(f"   Phishing:   {len(all_phishing)}")
    print(f"   Legitimate: {len(all_legitimate)}")

    # ------------------------------------------------------------------
    # Balance classes: use the smaller class size (or cap at total_rows/2)
    # ------------------------------------------------------------------
    target_per_class = min(total_rows // 2, len(all_phishing), len(all_legitimate))

    random.seed(42)
    random.shuffle(all_phishing)
    random.shuffle(all_legitimate)

    phishing_final = all_phishing[:target_per_class]
    legitimate_final = all_legitimate[:target_per_class]

    rows = []
    for text in phishing_final:
        rows.append({"text": text, "label": 1})
    for text in legitimate_final:
        rows.append({"text": text, "label": 0})

    random.shuffle(rows)

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] Multi-source dataset saved -> {output_path}")
    print(f"     Total samples: {len(rows)} (Phishing: {target_per_class}, Legitimate: {target_per_class})")
    print(f"     Sources: {', '.join(sources_used)}")
    return sources_used


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output = os.path.join(script_dir, "..", "..", "data", "phishing_dataset.csv")
    generate_dataset(output, total_rows=50000)
