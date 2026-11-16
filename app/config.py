"""Application configuration, read from environment variables.

Works locally (``.env`` file) and on Railway, which injects ``MYSQL*`` variables
for its MySQL plugin.
"""
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def _db_settings() -> dict:
    """Resolve MySQL settings from a URL or from individual variables."""
    url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if url:
        p = urlparse(url)
        return {
            "host": p.hostname or "127.0.0.1",
            "port": p.port or 3306,
            "user": unquote(p.username or ""),
            "password": unquote(p.password or ""),
            "database": (p.path or "/").lstrip("/"),
        }
    env = os.getenv
    return {
        "host": env("DB_HOST") or env("MYSQLHOST") or "127.0.0.1",
        "port": int(env("DB_PORT") or env("MYSQLPORT") or 3306),
        "user": env("DB_USER") or env("MYSQLUSER") or "root",
        "password": env("DB_PASSWORD") or env("MYSQLPASSWORD") or "",
        "database": env("DB_NAME") or env("MYSQLDATABASE") or "fileportal",
    }


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")
    DB = _db_settings()

    # Uploads: stored on the server's disk (mount a volume here in production).
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")).resolve()
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024  # whole-request cap

    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV", "production") != "development"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours
