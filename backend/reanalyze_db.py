import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import EmailRecord, SystemSettings
from app.ml.predict import predict_email

db: Session = SessionLocal()

emails = db.query(EmailRecord).all()
print(f"Found {len(emails)} emails to re-analyze.")

SPAM_MARKER = "\U0001f4c1"  # 📁 — folder-source marker appended by the ingest pipeline

for email in emails:
    res = predict_email(email.subject, email.body, email.sender)
    reasons = list(res["flagged_reasons"])
    try:
        old_reasons = json.loads(email.flagged_reasons_json) if email.flagged_reasons_json else []
    except (TypeError, ValueError):
        old_reasons = []
    # Preserve the source-folder note across re-scans
    reasons += [r for r in old_reasons if r.startswith(SPAM_MARKER)]
    email.risk_score = res["risk_score"]
    email.label = res["label"]
    email.flagged_reasons_json = json.dumps(reasons)
    
settings = db.query(SystemSettings).first()
if settings:
    settings.global_scanned = len(emails)
    settings.global_phishing = sum(1 for e in emails if e.label == "phishing")
    settings.global_suspicious = sum(1 for e in emails if e.label == "suspicious")

db.commit()
db.close()
print("Database re-analysis complete!")
