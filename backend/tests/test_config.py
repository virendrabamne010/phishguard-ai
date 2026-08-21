import os

from app.config import Settings


def test_settings_use_safe_defaults_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings()

    assert settings.ENVIRONMENT == "development"
    assert settings.SECRET_KEY == "dev-fallback-secret-key"
    assert settings.ADMIN_PASSWORD == "password123"
    assert settings.DATABASE_URL.startswith("sqlite://")
