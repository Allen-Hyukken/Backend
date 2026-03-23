import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Local dev fallback values ─────────────────────────────────────────────────
_DB_USER = os.getenv("DB_USER", "root")
_DB_PASS = os.getenv("DB_PASS", "12345")
_DB_HOST = os.getenv("DB_HOST", "localhost")
_DB_PORT = os.getenv("DB_PORT", "3306")
_DB_NAME = os.getenv("DB_NAME", "quizdatabase")

_DEFAULT_URL = f"mysql+pymysql://{_DB_USER}:{_DB_PASS}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"

# Railway injects MYSQL_URL automatically when you add a MySQL plugin.
# We prefer that over everything else.
_DATABASE_URL = (
    os.getenv("MYSQL_URL")        # Railway MySQL plugin — checked first
    or os.getenv("DATABASE_URL")  # manual override or local .env
    or _DEFAULT_URL               # local dev fallback
)

# Railway's MySQL URL starts with "mysql://" but SQLAlchemy needs "mysql+pymysql://"
if _DATABASE_URL.startswith("mysql://"):
    _DATABASE_URL = _DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)


def _build_connect_args() -> dict:
    """Use SSL on Railway (production), skip SSL locally."""
    is_production = os.getenv("RAILWAY_ENVIRONMENT") is not None
    args: dict = {
        "connect_timeout": 10,
        "read_timeout":    30,
        "write_timeout":   30,
    }
    if is_production:
        args["ssl"] = {"ssl_disabled": False}
    return args


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

    SQLALCHEMY_DATABASE_URI        = _DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS      = {
        "pool_pre_ping":  True,
        "pool_recycle":   1800,
        "pool_size":      5,
        "max_overflow":   10,
        "connect_args":   _build_connect_args(),
    }

    JWT_SECRET_KEY           = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    )

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB banner uploads