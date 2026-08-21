"""
config.py — Environment configuration and application settings.
"""

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(ROOT_DIR / ".env", override=False)


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    PROJECT_NAME: str = "PhishGuard AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    API_PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "False").lower() in ("true", "1", "t"))
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", ""), validate_default=True)
    ADMIN_USERNAME: str = Field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    ADMIN_PASSWORD: str = Field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""), validate_default=True)
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""), validate_default=True)
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])
    FRONTEND_URL: str = Field(default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:5173"))
    REDIRECT_URI: str = Field(default_factory=lambda: os.getenv("REDIRECT_URI", "http://localhost:8000/inbox/oauth/callback"))
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "testserver"])

    BASE_DIR: Path = BASE_DIR
    ROOT_DIR: Path = ROOT_DIR
    TOKEN_PATH: Path = BASE_DIR / "token.json"
    CREDENTIALS_PATH: Path = BASE_DIR / "credentials.json"
    REPORTED_PATH: Path = BASE_DIR / "reported_emails.json"
    DEMO_EMAILS_PATH: Path = BASE_DIR / "app" / "demo_emails.json"
    IMAP_SESSION_PATH: Path = BASE_DIR / "imap_session.json"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str, info: Any) -> str:
        debug = info.data.get("DEBUG", False)
        if not value:
            if debug:
                return "dev-fallback-secret-key"
            raise ValueError("SECRET_KEY must be set in production.")
        return value

    @field_validator("ADMIN_PASSWORD", mode="before")
    @classmethod
    def validate_admin_password(cls, value: Any, info: Any) -> str:
        if value is None:
            value = ""
        if not value:
            env = info.data.get("ENVIRONMENT", os.getenv("ENVIRONMENT", "development"))
            debug = info.data.get("DEBUG", False)
            if debug or env in ("development", "testing"):
                return "password123"
            raise ValueError("ADMIN_PASSWORD must be set in production.")
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def default_database_url(cls, value: Any) -> str:
        if value:
            return value
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = (data_dir / "phishguard.db").resolve()
        return f"sqlite:///{db_path.as_posix()}"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("TRUSTED_HOSTS", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value: Any) -> list[str]:
        if not value:
            return ["localhost", "127.0.0.1", "testserver"]
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @field_validator("TRUSTED_HOSTS")
    @classmethod
    def ensure_frontend_host_is_trusted(cls, value: list[str], info: Any) -> list[str]:
        frontend_url = info.data.get("FRONTEND_URL")
        if frontend_url:
            parsed = urlparse(frontend_url)
            if parsed.hostname and parsed.hostname not in value:
                value = [*value, parsed.hostname]
        return value


settings = Settings()
