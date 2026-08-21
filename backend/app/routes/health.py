"""
routes/health.py — Health check and readiness endpoints.
"""

import os
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/")
def root_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": settings.VERSION}


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": {"status": "ok"}}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@router.get("/health/gmail-setup")
def gmail_setup_status():
    """
    Returns whether Gmail OAuth is configured (credentials.json present)
    and whether the user is already connected (token.json present).
    """
    credentials_exist = os.path.exists(settings.CREDENTIALS_PATH)
    token_exists = os.path.exists(settings.TOKEN_PATH)
    return {
        "credentials_configured": credentials_exist,
        "gmail_connected": token_exists,
        "credentials_path_hint": "backend/credentials.json",
    }
