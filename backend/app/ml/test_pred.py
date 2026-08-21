import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.ml.predict import predict_email

test_emails = [
    {
        "subject": "Team Meeting Update",
        "body": "Hi everyone, the weekly sync is moved to 3 PM tomorrow. Please update your calendars.",
        "sender": "manager@company.com"
    },
    {
        "subject": "Lunch?",
        "body": "Are we still doing lunch today?",
        "sender": "colleague@company.com"
    },
    {
        "subject": "URGENT: Update your password immediately",
        "body": "Your account will be suspended. Click here to verify your identity.",
        "sender": "security@paypal-update.com"
    }
]

for email in test_emails:
    res = predict_email(email["subject"], email["body"], email["sender"])
    print(f"Subject: {email['subject']}")
    print(f"Risk Score: {res['risk_score']}")
    print(f"Label: {res['label']}")
    print(f"Reasons: {res['flagged_reasons']}")
    print("-" * 50)
