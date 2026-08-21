"""
routes/analytics.py — System analytics, audit log, database dump, and data export endpoints.
"""

import os
import io
import csv
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EmailRecord, SystemSettings, AdminUser, AuditLog
from app.schemas import (
    SystemAnalyticsResponse,
    DatabaseDumpResponse,
    AuditLogEntry,
    AuditLogResponse,
)
from app.deps import get_current_user, write_audit_log

router = APIRouter(prefix="/system", tags=["Analytics"])


def _get_or_create_settings(db: Session):
    sys_settings = db.query(SystemSettings).first()
    if not sys_settings:
        sys_settings = SystemSettings(mode="disconnected")
        db.add(sys_settings)
        db.commit()
        db.refresh(sys_settings)
    return sys_settings


@router.get("/analytics", response_model=SystemAnalyticsResponse)
def get_system_analytics(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    sys_settings = _get_or_create_settings(db)

    meta_path = os.path.join(settings.BASE_DIR, "app", "ml", "model_artifacts", "metadata.json")
    model_metrics = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                model_metrics = json.load(f)
        except Exception:
            pass

    return SystemAnalyticsResponse(
        global_scanned=sys_settings.global_scanned,
        global_phishing=sys_settings.global_phishing,
        global_suspicious=sys_settings.global_suspicious,
        model_metrics=model_metrics,
    )


@router.get("/database/dump", response_model=DatabaseDumpResponse)
def dump_database(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    sys_settings_list = db.query(SystemSettings).all()
    emails = db.query(EmailRecord).all()

    settings_out = [
        {
            "id": s.id,
            "mode": s.mode,
            "global_scanned": s.global_scanned,
            "global_phishing": s.global_phishing,
            "global_suspicious": s.global_suspicious,
        }
        for s in sys_settings_list
    ]

    emails_out = [
        {
            "id": e.id,
            "subject": e.subject,
            "sender": e.sender,
            "risk_score": e.risk_score,
            "label": e.label,
            "reported": e.reported,
        }
        for e in emails
    ]

    return DatabaseDumpResponse(settings=settings_out, emails=emails_out)


@router.get("/audit-log", response_model=AuditLogResponse)
def get_audit_log(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Return recent audit log entries, newest first."""
    entries = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(min(limit, 500))
        .all()
    )
    return AuditLogResponse(
        entries=[
            AuditLogEntry(
                id=e.id,
                timestamp=e.timestamp.isoformat() if e.timestamp else "",
                admin_username=e.admin_username,
                action=e.action,
                resource_id=e.resource_id,
                detail=e.detail,
                ip_address=e.ip_address,
            )
            for e in entries
        ]
    )


@router.get("/export/csv")
def export_emails_csv(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Export all email scan results as a downloadable CSV file."""
    emails = db.query(EmailRecord).filter(EmailRecord.deleted == False).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Subject", "Sender", "Risk Score", "Label", "Reported", "Flagged Reasons"])
    for e in emails:
        reasons = "; ".join(e.flagged_reasons) if e.flagged_reasons else ""
        writer.writerow([e.id, e.subject, e.sender, e.risk_score, e.label, e.reported, reasons])

    output.seek(0)
    write_audit_log(db, current_user.username, "export_csv")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=phishguard_report.csv"},
    )


@router.get("/export/json")
def export_emails_json(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Export all email scan results as a downloadable JSON file."""
    emails = db.query(EmailRecord).filter(EmailRecord.deleted == False).all()
    data = [
        {
            "id": e.id,
            "subject": e.subject,
            "sender": e.sender,
            "risk_score": e.risk_score,
            "label": e.label,
            "reported": e.reported,
            "flagged_reasons": e.flagged_reasons,
        }
        for e in emails
    ]
    write_audit_log(db, current_user.username, "export_json")
    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=phishguard_report.json"},
    )
