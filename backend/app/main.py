"""
main.py — Production-grade FastAPI application for Phishing Detection.
Fully typed with Pydantic response models, structured logging, custom exception handlers,
SQLite/PostgreSQL persistence, JWT Authentication (access + refresh tokens),
Real-Time WebSockets with auth, and multi-provider IMAP support.
"""

import os
import uuid
import json
import csv
import io
import asyncio
import base64
import hashlib
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Request, status, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import text, inspect, or_
from sqlalchemy.orm import Session
from jose import JWTError
from contextlib import asynccontextmanager
from cryptography.fernet import Fernet, InvalidToken
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings

limiter = Limiter(key_func=get_remote_address)

from app.logger import logger
from app.schemas import (
    InboxResponse,
    EmailDetailResponse,
    StatusResponse,
    ConnectResponse,
    ReportResponse,
    ActionStatusResponse,
    CustomAnalyzeRequest,
    CustomAnalyzeResponse,
    SystemAnalyticsResponse,
    DatabaseDumpResponse,
    Token,
    TokenRefresh,
    IMAPConnectRequest,
    ChangePasswordRequest,
    AuditLogEntry,
    AuditLogResponse,
)

from app.database import engine, Base, get_db, SessionLocal
from app.models import EmailRecord, SystemSettings, AdminUser, AuditLog
from app.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.imap_client import fetch_imap_emails


# ---------------------------------------------------------------------------
# WebSocket Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send WS message, marking connection dead: {e}")
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect(conn)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Lightweight Schema Auto-Migration
# ---------------------------------------------------------------------------
def _ensure_schema_upgrades(db_engine) -> None:
    """
    Add columns that exist on models but are missing from older databases.
    Base.metadata.create_all() creates missing TABLES but never ALTERS
    existing ones, which previously caused crashes like:
        'no such column: emails.created_at'
    """
    inspector = inspect(db_engine)

    expected_columns = {
        "emails": [
            ("reported", "BOOLEAN"),
            ("deleted", "BOOLEAN"),
            ("created_at", "TIMESTAMP"),
        ],
    }

    try:
        with db_engine.begin() as conn:
            for table, columns in expected_columns.items():
                if table not in inspector.get_table_names():
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(table)}
                for col_name, col_ddl in columns:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_ddl}"))
                        logger.info(f"Auto-migration: added column '{col_name}' to table '{table}'.")
            # Backfill boolean defaults so NULL rows are not hidden by filters
            conn.execute(text("UPDATE emails SET reported = FALSE WHERE reported IS NULL"))
            conn.execute(text("UPDATE emails SET deleted = FALSE WHERE deleted IS NULL"))
            # Remove legacy sequence-number email ids ('imap_<digits>') — replaced by
            # stable UIDs ('imap_u<digits>'). Old ids could collide after mail deletions.
            conn.execute(text(
                "DELETE FROM emails WHERE id LIKE 'imap\\_%' ESCAPE '\\' "
                "AND SUBSTR(id, 6, 1) BETWEEN '0' AND '9'"
            ))
    except Exception as e:
        logger.error(f"Schema auto-migration failed: {e}")


# ---------------------------------------------------------------------------
# FastAPI Initialization
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global active_imap_task

    Base.metadata.create_all(bind=engine)
    _ensure_schema_upgrades(engine)
    db = SessionLocal()
    try:
        admin_username = settings.ADMIN_USERNAME
        admin_password = settings.ADMIN_PASSWORD

        if not admin_password:
            if settings.DEBUG:
                admin_password = "password123"
                logger.warning("DEBUG mode active: using default admin credentials. Set ADMIN_PASSWORD for production.")
            else:
                raise RuntimeError("ADMIN_PASSWORD must be set in production.")

        existing_admin = db.query(AdminUser).filter(AdminUser.username == admin_username).first()
        if not existing_admin:
            hashed = get_password_hash(admin_password)
            admin = AdminUser(username=admin_username, hashed_password=hashed)
            db.add(admin)
            db.commit()
            logger.info(f"Seeded admin user '{admin_username}'.")
        elif not verify_password(admin_password, existing_admin.hashed_password):
            # Keep the stored hash in sync when ADMIN_PASSWORD changes in .env
            existing_admin.hashed_password = get_password_hash(admin_password)
            db.commit()
            logger.info(f"Synced password for admin '{admin_username}' from ADMIN_PASSWORD setting.")

        # Auto-resume the persisted IMAP session (if any) so live emails keep flowing
        saved_session = _load_imap_session()
        if saved_session:
            sys_settings = _get_or_create_settings(db)
            if sys_settings.mode != "gmail":
                sys_settings.mode = "imap"
                db.commit()
            if active_imap_task and not active_imap_task.done():
                active_imap_task.cancel()
            active_imap_task = asyncio.create_task(
                imap_monitor_loop(
                    saved_session.get("email", ""),
                    saved_session.get("password", ""),
                    saved_session.get("provider", "gmail"),
                    saved_session.get("host"),
                    int(saved_session.get("port", 993)),
                )
            )
            logger.info("Auto-resumed IMAP monitoring daemon from saved session.")
    finally:
        db.close()

    try:
        yield
    finally:
        # Cleanly stop the IMAP daemon on shutdown
        if active_imap_task and not active_imap_task.done():
            active_imap_task.cancel()
            try:
                await active_imap_task
            except (asyncio.CancelledError, Exception):
                pass
            logger.info("IMAP monitoring daemon stopped on shutdown.")


tags_metadata = [
    {"name": "Auth", "description": "Authentication and JWT tokens."},
    {"name": "Inbox", "description": "Operations with the active email session."},
    {"name": "Emails", "description": "Retrieve and manage specific emails."},
    {"name": "OAuth", "description": "Google OAuth authentication endpoints."},
    {"name": "Health", "description": "System health and status."},
    {"name": "Analytics", "description": "Global system telemetry and ML metrics."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    **PhishGuard AI** is an advanced, machine-learning powered email phishing detection system.

    ## Features
    * Real-time IMAP email scanning (Gmail, Outlook, Yahoo, and custom servers)
    * ML-based Phishing Classification (TF-IDF + Logistic Regression with 60% weight)
    * Trusted domain allowlist — major providers are never false-flagged
    * Admin Dashboard and Threat Analytics
    * JWT Authentication with refresh token support
    * Real-time WebSocket threat alerts
    """,
    version=settings.VERSION,
    openapi_tags=tags_metadata,
    contact={"name": "Security Team", "email": "security@phishguard.ai"},
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)


@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    """Add security headers and a unique X-Request-ID to every response."""
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.redoc.ly; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' ws: wss:; "
        "img-src 'self' data: https:; "
        "worker-src 'self' blob:;"
    )
    return response


# ---------------------------------------------------------------------------
# Auth Setup
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        if username is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP Exception [{exc.status_code}] on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "path": request.url.path},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected server error occurred.", "path": request.url.path},
    )


# ---------------------------------------------------------------------------
# Lazy ML & Gmail Client Imports
# ---------------------------------------------------------------------------
def _get_predictor():
    from app.ml.predict import predict_email
    return predict_email


def _get_gmail_client():
    from app import gmail_client
    return gmail_client


# ---------------------------------------------------------------------------
# DB Helpers
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
# Background Processing Task
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

            # Surface the source folder when the mail came from Spam/Junk
            flagged_reasons = list(result["flagged_reasons"])
            source_folder = (email_item.get("folder") or "").lower()
            if source_folder and source_folder != "inbox":
                flagged_reasons.append(
                    f"📁 Retrieved from mail server's '{email_item['folder']}' (Spam/Junk) folder"
                )

            record = EmailRecord(
                id=email_item["id"],
                subject=email_item["subject"],
                sender=email_item["sender"],
                snippet=email_item.get("snippet", email_item["body"][:100]),
                body=email_item["body"],
                risk_score=result["risk_score"],
                label=result["label"],
                flagged_reasons_json=json.dumps(flagged_reasons),
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
                    "id": record.id,
                    "subject": record.subject,
                    "sender": record.sender,
                    "snippet": record.snippet,
                    "risk_score": record.risk_score,
                    "label": record.label,
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
# IMAP Background Daemon
# ---------------------------------------------------------------------------
active_imap_task = None
_imap_session: dict = {}  # Stores current IMAP session config (not password in logs)


def _save_imap_session(email: str, password: str, provider: str, host: str | None, port: int):
    """Persist the active IMAP session to disk so it survives backend restarts."""
    global _imap_session
    session_data = {
        "email": email,
        "password": password,
        "provider": provider,
        "host": host,
        "port": port,
    }
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
    """Load the persisted IMAP session, if any. Returns None if not present."""
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
            # Backward-compatible migration path for legacy plaintext files.
            data = raw_data
            if data.get("password"):
                _save_imap_session(
                    data.get("email", ""),
                    data.get("password", ""),
                    data.get("provider", "gmail"),
                    data.get("host"),
                    int(data.get("port", 993)),
                )
        _imap_session = {
            "email": data.get("email", ""),
            "provider": data.get("provider", "gmail"),
            "host": data.get("host"),
            "port": data.get("port", 993),
        }
        return data
    except (InvalidToken, KeyError) as e:
        logger.error(f"Failed to decrypt IMAP session: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load IMAP session: {e}")
        return None


def _clear_imap_session():
    """Remove the persisted IMAP session (used on disconnect)."""
    global _imap_session
    _imap_session = {}
    try:
        if os.path.exists(settings.IMAP_SESSION_PATH):
            os.remove(settings.IMAP_SESSION_PATH)
            logger.info("IMAP session cleared.")
    except Exception as e:
        logger.error(f"Failed to clear IMAP session: {e}")


async def _imap_poll_once(email_address: str, password: str, provider: str, imap_host: str | None, imap_port: int) -> int:
    """
    Perform a single IMAP fetch and process any new emails.
    Returns the number of new emails processed.
    """
    new_emails = await asyncio.to_thread(
        fetch_imap_emails,
        email_address,
        password,
        20,
        provider,
        imap_host,
        imap_port,
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
    """
    Live IMAP monitor daemon. Fetches immediately on start, then polls every 30s.
    Runs forever until cancelled (on shutdown or manual disconnect).
    """
    logger.info(f"Started IMAP monitor daemon for {email_address} (provider={provider})")

    # Immediate fetch so the inbox populates as soon as the system starts
    try:
        await _imap_poll_once(email_address, password, provider, imap_host, imap_port)
    except Exception as e:
        logger.error(f"IMAP initial fetch error: {e}")

    while True:
        try:
            await asyncio.sleep(15)  # Poll every 15 seconds for near-real-time delivery

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
# API Routes — Auth
# ---------------------------------------------------------------------------

@app.post("/auth/login", response_model=Token, tags=["Auth"])
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(AdminUser).filter(AdminUser.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(data={"sub": user.username})
    _write_audit_log(
        db,
        user.username,
        "login_success",
        ip_address=request.client.host if request.client else None,
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@app.post("/auth/refresh", response_model=Token, tags=["Auth"])
@limiter.limit("10/minute")
def refresh_access_token(request: Request, body: TokenRefresh, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(body.refresh_token)
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "")
        if username is None or token_type != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        raise credentials_exception

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# API Routes — WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if not username:
            raise JWTError()
        db = SessionLocal()
        try:
            user = db.query(AdminUser).filter(AdminUser.username == username).first()
        finally:
            db.close()
        if user is None:
            raise JWTError()
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# API Routes — Health
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": settings.VERSION}


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/ready", tags=["Health"])
def readiness_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": {"status": "ok"}}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/health/gmail-setup", tags=["Health"])
def gmail_setup_status():
    """
    Returns whether Gmail OAuth is configured (credentials.json present)
    and whether the user is already connected (token.json present).
    Used by the frontend to show a setup guide instead of a vague error.
    """
    credentials_exist = os.path.exists(settings.CREDENTIALS_PATH)
    token_exists = os.path.exists(settings.TOKEN_PATH)
    return {
        "credentials_configured": credentials_exist,
        "gmail_connected": token_exists,
        "credentials_path_hint": "backend/credentials.json",
    }


# ---------------------------------------------------------------------------
# API Routes — Inbox
# ---------------------------------------------------------------------------

@app.get("/inbox/status", response_model=StatusResponse, tags=["Inbox"])
def get_status(db: Session = Depends(get_db), current_user: AdminUser = Depends(get_current_user)):
    sys_settings = _get_or_create_settings(db)
    email_count = db.query(EmailRecord).count()
    return StatusResponse(
        mode=sys_settings.mode,
        email_count=email_count,
        environment=settings.ENVIRONMENT,
        connected_email=_imap_session.get("email") or None,
        provider=_imap_session.get("provider") or None,
    )


@app.post("/inbox/demo", response_model=ActionStatusResponse, tags=["Inbox"])
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


@app.get("/inbox/connect", response_model=ConnectResponse, tags=["OAuth"])
def connect_gmail(current_user: AdminUser = Depends(get_current_user)):
    try:
        gmail = _get_gmail_client()
        auth_url = gmail.get_auth_url()
        return ConnectResponse(auth_url=auth_url)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="OAuth initialization failed.")


@app.get("/inbox/oauth/callback", tags=["OAuth"])
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


@app.post("/inbox/fetch", response_model=ActionStatusResponse, tags=["Inbox"])
async def fetch_gmail_emails(
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


@app.post("/inbox/imap/connect", response_model=ActionStatusResponse, tags=["Inbox"])
async def connect_imap_endpoint(
    payload: IMAPConnectRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    global active_imap_task, _imap_session

    try:
        new_emails = await asyncio.to_thread(
            fetch_imap_emails,
            payload.email,
            payload.password,
            20,
            payload.provider,
            payload.imap_host,
            payload.imap_port,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IMAP Connection failed: {str(e)}")

    sys_settings = _get_or_create_settings(db)
    sys_settings.mode = "imap"
    db.commit()

    # Persist session so the daemon auto-resumes after backend restart
    _save_imap_session(payload.email, payload.password, payload.provider, payload.imap_host, payload.imap_port)

    # Gracefully stop any existing daemon before spawning a new one
    if active_imap_task and not active_imap_task.done():
        active_imap_task.cancel()

    # Spawn background monitoring daemon
    active_imap_task = asyncio.create_task(
        imap_monitor_loop(
            payload.email,
            payload.password,
            payload.provider,
            payload.imap_host,
            payload.imap_port,
        )
    )

    if new_emails:
        existing_ids = {r.id for r in db.query(EmailRecord.id).all()}
        unique_emails = [e for e in new_emails if e["id"] not in existing_ids]
        if unique_emails:
            background_tasks.add_task(process_emails_bg, unique_emails)
            return ActionStatusResponse(status="imap_processing_started", email_count=len(unique_emails))

    return ActionStatusResponse(status="imap_connected", email_count=0)


@app.post("/inbox/imap/refresh", response_model=ActionStatusResponse, tags=["Inbox"])
async def refresh_imap_emails(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """
    Manually check the connected IMAP account for new emails.
    Works even if the background daemon isn't running (uses the saved session).
    """
    global active_imap_task

    if active_imap_task and not active_imap_task.done():
        # Daemon is running — do a one-off immediate poll
        session_data = _imap_session
        if not session_data.get("email"):
            raise HTTPException(status_code=400, detail="No active IMAP session. Connect an account first.")
        new_count = await _imap_poll_once(
            session_data["email"],
            _get_saved_password(),
            session_data.get("provider", "gmail"),
            session_data.get("host"),
            int(session_data.get("port", 993)),
        )
        if new_count:
            await manager.broadcast({"event": "stats_updated"})
        return ActionStatusResponse(status="imap_refreshed", email_count=new_count)

    # Daemon not running — try to resume from saved session
    saved_session = _load_imap_session()
    if not saved_session:
        raise HTTPException(status_code=400, detail="No saved IMAP session. Connect an account first.")

    sys_settings = _get_or_create_settings(db)
    sys_settings.mode = "imap"
    db.commit()

    active_imap_task = asyncio.create_task(
        imap_monitor_loop(
            saved_session.get("email", ""),
            saved_session.get("password", ""),
            saved_session.get("provider", "gmail"),
            saved_session.get("host"),
            int(saved_session.get("port", 993)),
        )
    )
    return ActionStatusResponse(status="imap_resumed", email_count=0)


def _get_saved_password() -> str:
    """Read the saved IMAP password from disk (needed when only the daemon session exists)."""
    try:
        data = _load_imap_session()
        if data:
            return data.get("password", "")
    except Exception:
        pass
    return ""


@app.post("/inbox/imap/disconnect", response_model=ActionStatusResponse, tags=["Inbox"])
async def disconnect_imap_endpoint(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Stop the live IMAP monitor daemon and clear the saved session."""
    global active_imap_task

    if active_imap_task and not active_imap_task.done():
        active_imap_task.cancel()
        active_imap_task = None

    _clear_imap_session()

    sys_settings = _get_or_create_settings(db)
    if sys_settings.mode == "imap":
        # Keep the emails in the DB but switch mode so the UI reflects disconnect state
        sys_settings.mode = "disconnected"
        db.commit()

    return ActionStatusResponse(status="imap_disconnected", email_count=0)


@app.post("/inbox/imap/backfill", response_model=ActionStatusResponse, tags=["Inbox"])
async def backfill_imap_emails(
    days: int = 10,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Scan past N days of emails and process them in the background."""
    session_data = _load_imap_session()
    if not session_data or not session_data.get("email"):
        raise HTTPException(status_code=400, detail="No active IMAP session. Connect an account first.")
        
    try:
        raw_emails = await asyncio.to_thread(
            fetch_imap_emails,
            session_data["email"],
            session_data.get("password", ""),
            limit=500,  # Higher limit for backfill
            provider=session_data.get("provider", "gmail"),
            imap_host=session_data.get("host"),
            imap_port=int(session_data.get("port", 993)),
            days_back=days,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical emails: {str(e)}")

    existing_ids = {r.id for r in db.query(EmailRecord.id).all()}
    new_emails = [e for e in raw_emails if e["id"] not in existing_ids]

    if new_emails:
        background_tasks.add_task(process_emails_bg, new_emails)

    return ActionStatusResponse(status="imap_backfill_started", email_count=len(new_emails))



# ---------------------------------------------------------------------------
# API Routes — Emails
# ---------------------------------------------------------------------------

@app.get("/inbox/emails", response_model=InboxResponse, tags=["Emails"])
def get_emails(db: Session = Depends(get_db), current_user: AdminUser = Depends(get_current_user)):
    sys_settings = _get_or_create_settings(db)
    if sys_settings.mode == "disconnected":
        return InboxResponse(mode="disconnected", emails=[], message="Connect Gmail or use Demo Mode")

    records = db.query(EmailRecord).filter(EmailRecord.deleted == False).all()
    emails_list = [
        {
            "id": r.id,
            "subject": r.subject,
            "sender": r.sender,
            "snippet": r.snippet,
            "risk_score": r.risk_score,
            "label": r.label,
            "flagged_reasons": r.flagged_reasons,
            "suspicious_keywords": r.suspicious_keywords,
            "reported": r.reported,
        }
        for r in records
    ]

    emails_list.reverse()
    return InboxResponse(mode=sys_settings.mode, emails=emails_list)


@app.get("/inbox/emails/search", response_model=InboxResponse, tags=["Emails"])
def search_emails(
    q: str = "",
    label: str = "",
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Search and filter emails by text query and/or label."""
    sys_settings = _get_or_create_settings(db)
    query = db.query(EmailRecord).filter(EmailRecord.deleted == False)

    if label and label in ["phishing", "suspicious", "legitimate"]:
        query = query.filter(EmailRecord.label == label)

    # SQL-level text search (works with both SQLite and PostgreSQL via ILIKE)
    q_lower = q.lower().strip()
    if q_lower:
        pattern = f"%{q_lower}%"
        query = query.filter(
            or_(
                EmailRecord.subject.ilike(pattern),
                EmailRecord.sender.ilike(pattern),
                EmailRecord.snippet.ilike(pattern),
            )
        )

    records = query.all()

    emails_list = [
        {
            "id": r.id,
            "subject": r.subject,
            "sender": r.sender,
            "snippet": r.snippet,
            "risk_score": r.risk_score,
            "label": r.label,
            "flagged_reasons": r.flagged_reasons,
            "suspicious_keywords": r.suspicious_keywords,
            "reported": r.reported,
        }
        for r in records
    ]
    emails_list.reverse()

    return InboxResponse(mode=sys_settings.mode, emails=emails_list)



@app.get("/inbox/emails/{email_id}", response_model=EmailDetailResponse, tags=["Emails"])
def get_email_detail(
    email_id: str,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    record = db.query(EmailRecord).filter(EmailRecord.id == email_id).first()
    if record:
        return EmailDetailResponse(
            id=record.id,
            subject=record.subject,
            sender=record.sender,
            snippet=record.snippet,
            body=record.body,
            risk_score=record.risk_score,
            label=record.label,
            flagged_reasons=record.flagged_reasons,
            suspicious_keywords=record.suspicious_keywords,
            reported=record.reported,
        )
    raise HTTPException(status_code=404, detail="Email not found.")


@app.post("/inbox/emails/{email_id}/report", response_model=ReportResponse, tags=["Emails"])
def report_email(
    request: Request,
    email_id: str,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    record = db.query(EmailRecord).filter(EmailRecord.id == email_id, EmailRecord.deleted == False).first()
    if not record:
        raise HTTPException(status_code=404, detail="Email not found.")
    record.reported = True
    db.commit()
    _write_audit_log(
        db,
        current_user.username,
        "report_email",
        resource_id=email_id,
        detail=f"Marked '{record.subject}' as reported.",
        ip_address=request.client.host if request.client else None,
    )
    return ReportResponse(status="reported", email_id=email_id, message="Reported successfully.")


@app.delete("/inbox/emails/{email_id}", response_model=ActionStatusResponse, tags=["Emails"])
def delete_email(
    request: Request,
    email_id: str,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    record = db.query(EmailRecord).filter(EmailRecord.id == email_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Email not found.")

    # Soft delete
    record.deleted = True
    db.commit()
    _write_audit_log(
        db,
        current_user.username,
        "delete_email",
        resource_id=email_id,
        detail=f"Soft-deleted '{record.subject}'.",
        ip_address=request.client.host if request.client else None,
    )
    return ActionStatusResponse(status="deleted", email_count=1)


@app.post("/inbox/analyze", response_model=CustomAnalyzeResponse, tags=["Emails"])
@limiter.limit("10/minute")
async def analyze_custom_email(
    request: Request,
    payload: CustomAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    predict = _get_predictor()
    result = predict(
        subject=payload.subject,
        body=payload.body,
        sender=payload.sender,
    )

    sys_settings = _get_or_create_settings(db)
    if sys_settings.mode == "disconnected":
        sys_settings.mode = "demo"
        db.commit()

    email_count = db.query(EmailRecord).count()
    custom_id = f"custom_{email_count + 1:03d}"

    record = EmailRecord(
        id=custom_id,
        subject=payload.subject or "(No Subject)",
        sender=payload.sender or "unknown@domain.com",
        snippet=payload.body[:100],
        body=payload.body,
        risk_score=result["risk_score"],
        label=result["label"],
        flagged_reasons_json=json.dumps(result["flagged_reasons"]),
        suspicious_keywords_json=json.dumps(result.get("suspicious_keywords", [])),
        reported=False,
    )
    db.add(record)
    db.commit()
    _update_global_stats(db, [result])

    await manager.broadcast({
        "event": "new_email",
        "data": {
            "id": record.id,
            "subject": record.subject,
            "sender": record.sender,
            "snippet": record.snippet,
            "risk_score": record.risk_score,
            "label": record.label,
            "flagged_reasons": result["flagged_reasons"],
            "suspicious_keywords": result.get("suspicious_keywords", []),
            "reported": record.reported,
        },
    })

    return CustomAnalyzeResponse(
        subject=record.subject,
        sender=record.sender,
        body=record.body,
        risk_score=record.risk_score,
        label=record.label,
        flagged_reasons=record.flagged_reasons,
        suspicious_keywords=record.suspicious_keywords,
    )


# ---------------------------------------------------------------------------
# API Routes — Analytics
# ---------------------------------------------------------------------------

@app.get("/system/analytics", response_model=SystemAnalyticsResponse, tags=["Analytics"])
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


@app.get("/system/database/dump", response_model=DatabaseDumpResponse, tags=["Analytics"])
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


# ---------------------------------------------------------------------------
# Audit Log Helper
# ---------------------------------------------------------------------------
def _write_audit_log(
    db: Session,
    username: str,
    action: str,
    resource_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
):
    """Write a single audit log entry. Never raises — logs the error instead."""
    try:
        entry = AuditLog(
            admin_username=username,
            action=action,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
        db.rollback()


# ---------------------------------------------------------------------------
# Auth — Change Password
# ---------------------------------------------------------------------------
@app.post("/auth/change-password", tags=["Auth"])
@limiter.limit("5/minute")
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    """Change the admin password. Requires current password for verification."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    current_user.hashed_password = get_password_hash(body.new_password)
    db.commit()

    _write_audit_log(
        db, current_user.username, "change_password",
        ip_address=request.client.host if request.client else None,
    )
    logger.info(f"Admin '{current_user.username}' changed their password.")
    return {"status": "ok", "message": "Password changed successfully."}


# ---------------------------------------------------------------------------
# Audit Log — View
# ---------------------------------------------------------------------------
@app.get("/system/audit-log", response_model=AuditLogResponse, tags=["Analytics"])
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


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------
@app.get("/system/export/csv", tags=["Analytics"])
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
    _write_audit_log(db, current_user.username, "export_csv")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=phishguard_report.csv"},
    )


@app.get("/system/export/json", tags=["Analytics"])
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
    _write_audit_log(db, current_user.username, "export_json")
    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=phishguard_report.json"},
    )
