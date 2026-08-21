"""
routes/inbox.py — IMAP connection, Gmail OAuth, demo mode, and background monitoring.
"""

import os
import json
import asyncio
import base64
import hashlib

from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import EmailRecord, SystemSettings, AdminUser
from app.schemas import (
    StatusResponse,
    ConnectResponse,
    ActionStatusResponse,
    IMAPConnectRequest,
)
from app.imap_client import fetch_imap_emails
from app.logger import logger
from app.deps import get_current_user, manager

router = APIRouter(prefix="/inbox", tags=["Inbox"])

# ---------------------------------------------------------------------------
# Module-level state for IMAP daemon
# ---------------------------------------------------------------------------
active_imap_task = None
_imap_session: dict = {}


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------
def _get_predictor():
    from app.ml.predict import predict_email
    return predict_email


def _get_gmail_client():
    from app import gmail_client
    return gmail_client


# ---------------------------------------------------------------------------
# DB / Crypto helpers
# ---------------------------------------------------------------------------
def _get_or_create_settings(db: Session):
    sys_settings = db.query(SystemSettings).first()
    if not sys_settings:
        sys_settings = SystemSettings(mode="disconnected")
        db.add(sys_settings)
        db.commit()
        db.refresh(sys_settings)
    return sys_settings


def _update_global_stats(db: Session, emails: list):
    sys_settings = _get_or_create_settings(db)
    sys_settings.global_scanned += len(emails)
    for e in emails:
        if e.get("label") == "phishing":
            sys_settings.global_phishing += 1
        elif e.get("label") == "suspicious":
            sys_settings.global_suspicious += 1
    db.commit()


def _get_imap_cipher() -> Fernet:
    key_material = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


# ---------------------------------------------------------------------------
# IMAP Session Persistence (encrypted)
# ---------------------------------------------------------------------------
def _save_imap_session(email: str, password: str, provider: str, host: str | None, port: int):
    global _imap_session
    session_data = {"email": email, "password": password, "provider": provider, "host": host, "port": port}
    _imap_session = {"email": email, "provider": provider, "host": host, "port": port}
    try:
        os.makedirs(settings.BASE_DIR, exist_ok=True)
        cipher = _get_imap_cipher()
        encrypted_payload = cipher.encrypt(json.dumps(session_data).encode("utf-8")).decode("utf-8")
        with open(settings.IMAP_SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "encrypted": True, "payload": encrypted_payload}, f, indent=2)
        logger.info(f"IMAP session saved for {email} (provider={provider}).")
    except Exception as e:
        logger.error(f"Failed to save IMAP session: {e}")


def _load_imap_session() -> dict | None:
    global _imap_session
    if not os.path.exists(settings.IMAP_SESSION_PATH):
        return None
    try:
        with open(settings.IMAP_SESSION_PATH, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        if raw_data.get("encrypted"):
            cipher = _get_imap_cipher()
            decrypted = cipher.decrypt(raw_data["payload"].encode("utf-8")).decode("utf-8")
            data = json.loads(decrypted)
        else:
            data = raw_data
            if data.get("password"):
                _save_imap_session(
                    data.get("email", ""), data.get("password", ""),
                    data.get("provider", "gmail"), data.get("host"),
                    int(data.get("port", 993)),
                )
        _imap_session = {
            "email": data.get("email", ""), "provider": data.get("provider", "gmail"),
            "host": data.get("host"), "port": data.get("port", 993),
        }
        return data
    except (InvalidToken, KeyError) as e:
        logger.error(f"Failed to decrypt IMAP session: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load IMAP session: {e}")
        return None


def _clear_imap_session():
    global _imap_session
    _imap_session = {}
    try:
        if os.path.exists(settings.IMAP_SESSION_PATH):
            os.remove(settings.IMAP_SESSION_PATH)
            logger.info("IMAP session cleared.")
    except Exception as e:
        logger.error(f"Failed to clear IMAP session: {e}")


def _get_saved_password() -> str:
    try:
        data = _load_imap_session()
        if data:
            return data.get("password", "")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Background Processing
# ---------------------------------------------------------------------------
async def process_emails_bg(emails: list):
    predict = _get_predictor()
    db = SessionLocal()
    try:
        analyzed_data = []
        for email_item in emails:
            result = predict(
                subject=email_item["subject"],
                body=email_item["body"],
                sender=email_item["sender"],
            )
            record = EmailRecord(
                id=email_item["id"],
                subject=email_item["subject"],
                sender=email_item["sender"],
                snippet=email_item.get("snippet", email_item["body"][:100]),
                body=email_item["body"],
                risk_score=result["risk_score"],
                label=result["label"],
                flagged_reasons_json=json.dumps(result["flagged_reasons"]),
                suspicious_keywords_json=json.dumps(result.get("suspicious_keywords", [])),
                reported=False,
            )
            try:
                db.add(record)
                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.warning(f"Skipping duplicate or failed email {record.id}: {db_err}")
                continue

            analyzed_data.append(result)

            payload = {
                "event": "new_email",
                "data": {
                    "id": record.id, "subject": record.subject, "sender": record.sender,
                    "snippet": record.snippet, "risk_score": record.risk_score, "label": record.label,
                    "flagged_reasons": result["flagged_reasons"],
                    "suspicious_keywords": result.get("suspicious_keywords", []),
                    "reported": record.reported,
                },
            }
            await asyncio.sleep(0.3)
            await manager.broadcast(payload)

        _update_global_stats(db, analyzed_data)
        await manager.broadcast({"event": "stats_updated"})
    except Exception as e:
        logger.error(f"Background task failed: {e}", exc_info=True)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# IMAP Monitor Daemon
# ---------------------------------------------------------------------------
async def _imap_poll_once(email_address: str, password: str, provider: str, imap_host: str | None, imap_port: int) -> int:
    new_emails = await asyncio.to_thread(
        fetch_imap_emails, email_address, password, 20, provider, imap_host, imap_port,
    )
    if not new_emails:
        return 0
    db = SessionLocal()
    try:
        existing_ids = {r.id for r in db.query(EmailRecord.id).all()}
        unique_emails = [e for e in new_emails if e["id"] not in existing_ids]
        if unique_emails:
            logger.info(f"IMAP found {len(unique_emails)} new emails! Processing...")
            await process_emails_bg(unique_emails)
            return len(unique_emails)
        return 0
    finally:
        db.close()


async def imap_monitor_loop(email_address: str, password: str, provider: str, imap_host: str | None, imap_port: int):
    logger.info(f"Started IMAP monitor daemon for {email_address} (provider={provider})")
    try:
        await _imap_poll_once(email_address, password, provider, imap_host, imap_port)
    except Exception as e:
        logger.error(f"IMAP initial fetch error: {e}")

    while True:
        try:
            await asyncio.sleep(30)
            new_count = await _imap_poll_once(email_address, password, provider, imap_host, imap_port)
            if new_count:
                await manager.broadcast({"event": "stats_updated"})
        except asyncio.CancelledError:
            logger.info("IMAP monitor daemon stopped.")
            break
        except Exception as e:
            logger.error(f"IMAP monitor error: {e}")
            await asyncio.sleep(30)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/status", response_model=StatusResponse)
def get_status(db: Session = Depends(get_db), current_user: AdminUser = Depends(get_current_user)):
    sys_settings = _get_or_create_settings(db)
    email_count = db.query(EmailRecord).count()
    return StatusResponse(mode=sys_settings.mode, email_count=email_count, environment=settings.ENVIRONMENT)


@router.post("/demo", response_model=ActionStatusResponse)
async def activate_demo(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    if not os.path.exists(settings.DEMO_EMAILS_PATH):
        raise HTTPException(status_code=500, detail="Demo emails resource file not found.")
    try:
        with open(settings.DEMO_EMAILS_PATH, "r", encoding="utf-8") as f:
            demo_emails = json.load(f)
        db.query(EmailRecord).delete()
        sys_settings = _get_or_create_settings(db)
        sys_settings.mode = "demo"
        db.commit()
        background_tasks.add_task(process_emails_bg, demo_emails)
        return ActionStatusResponse(status="demo_processing_started", email_count=len(demo_emails))
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to initialize Demo Mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize Demo Mode.")


@router.get("/connect", response_model=ConnectResponse, tags=["OAuth"])
def connect_gmail(current_user: AdminUser = Depends(get_current_user)):
    try:
        gmail = _get_gmail_client()
        auth_url = gmail.get_auth_url()
        return ConnectResponse(auth_url=auth_url)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="OAuth initialization failed.")


@router.get("/oauth/callback", tags=["OAuth"])
def oauth_callback(code: str, db: Session = Depends(get_db)):
    gmail = _get_gmail_client()
    success = gmail.handle_callback(code)
    if success:
        sys_settings = _get_or_create_settings(db)
        sys_settings.mode = "gmail"
        db.commit()
        redirect_url = settings.FRONTEND_URL.rstrip("/")
        return RedirectResponse(url=f"{redirect_url}?auth=success")
    else:
        raise HTTPException(status_code=400, detail="OAuth authorization code exchange failed.")


@router.post("/fetch", response_model=ActionStatusResponse)
async def fetch_gmail_emails_endpoint(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    gmail = _get_gmail_client()
    if not gmail.is_connected():
        raise HTTPException(status_code=400, detail="Gmail is not connected.")
    try:
        raw_emails = gmail.fetch_emails(max_results=20)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")
    sys_settings = _get_or_create_settings(db)
    sys_settings.mode = "gmail"
    db.commit()
    existing_ids = {r.id for r in db.query(EmailRecord.id).all()}
    new_emails = [e for e in raw_emails if e["id"] not in existing_ids]
    if new_emails:
        background_tasks.add_task(process_emails_bg, new_emails)
    return ActionStatusResponse(status="emails_processing_started", email_count=len(new_emails))


@router.post("/imap/connect", response_model=ActionStatusResponse)
async def connect_imap_endpoint(
    payload: IMAPConnectRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    global active_imap_task
    try:
        new_emails = await asyncio.to_thread(
            fetch_imap_emails, payload.email, payload.password, 20,
            payload.provider, payload.imap_host, payload.imap_port,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IMAP Connection failed: {str(e)}")

    sys_settings = _get_or_create_settings(db)
    sys_settings.mode = "imap"
    db.commit()
    _save_imap_session(payload.email, payload.password, payload.provider, payload.imap_host, payload.imap_port)

    if active_imap_task and not active_imap_task.done():
        active_imap_task.cancel()
    active_imap_task = asyncio.create_task(
        imap_monitor_loop(payload.email, payload.password, payload.provider, payload.imap_host, payload.imap_port)
    )

    if new_emails:
        existing_ids = {r.id for r in db.query(EmailRecord.id).all()}
        unique_emails = [e for e in new_emails if e["id"] not in existing_ids]
        if unique_emails:
            background_tasks.add_task(process_emails_bg, unique_emails)
            return ActionStatusResponse(status="imap_processing_started", email_count=len(unique_emails))
    return ActionStatusResponse(status="imap_connected", email_count=0)


@router.post("/imap/refresh", response_model=ActionStatusResponse)
async def refresh_imap_emails(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    global active_imap_task
    if active_imap_task and not active_imap_task.done():
        session_data = _imap_session
        if not session_data.get("email"):
            raise HTTPException(status_code=400, detail="No active IMAP session. Connect an account first.")
        new_count = await _imap_poll_once(
            session_data["email"], _get_saved_password(),
            session_data.get("provider", "gmail"), session_data.get("host"),
            int(session_data.get("port", 993)),
        )
        if new_count:
            await manager.broadcast({"event": "stats_updated"})
        return ActionStatusResponse(status="imap_refreshed", email_count=new_count)

    saved_session = _load_imap_session()
    if not saved_session:
        raise HTTPException(status_code=400, detail="No saved IMAP session. Connect an account first.")
    sys_settings = _get_or_create_settings(db)
    sys_settings.mode = "imap"
    db.commit()
    active_imap_task = asyncio.create_task(
        imap_monitor_loop(
            saved_session.get("email", ""), saved_session.get("password", ""),
            saved_session.get("provider", "gmail"), saved_session.get("host"),
            int(saved_session.get("port", 993)),
        )
    )
    return ActionStatusResponse(status="imap_resumed", email_count=0)


@router.post("/imap/disconnect", response_model=ActionStatusResponse)
async def disconnect_imap_endpoint(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    global active_imap_task
    if active_imap_task and not active_imap_task.done():
        active_imap_task.cancel()
        active_imap_task = None
    _clear_imap_session()
    sys_settings = _get_or_create_settings(db)
    if sys_settings.mode == "imap":
        sys_settings.mode = "disconnected"
        db.commit()
    return ActionStatusResponse(status="imap_disconnected", email_count=0)


@router.post("/imap/backfill", response_model=ActionStatusResponse)
async def backfill_imap_emails(
    days: int = 10,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    session_data = _load_imap_session()
    if not session_data or not session_data.get("email"):
        raise HTTPException(status_code=400, detail="No active IMAP session. Connect an account first.")
    try:
        raw_emails = await asyncio.to_thread(
            fetch_imap_emails, session_data["email"], session_data.get("password", ""),
            limit=500, provider=session_data.get("provider", "gmail"),
            imap_host=session_data.get("host"), imap_port=int(session_data.get("port", 993)),
            days_back=days,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical emails: {str(e)}")
    existing_ids = {r.id for r in db.query(EmailRecord.id).all()}
    new_emails = [e for e in raw_emails if e["id"] not in existing_ids]
    if new_emails:
        background_tasks.add_task(process_emails_bg, new_emails)
    return ActionStatusResponse(status="imap_backfill_started", email_count=len(new_emails))
