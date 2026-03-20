import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Read individual env vars so you can override just one thing ───────────────
_DB_USER = os.getenv("DB_USER", "root")
_DB_PASS = os.getenv("DB_PASS", "12345")      # ← change this if your MySQL
_DB_HOST = os.getenv("DB_HOST", "localhost")  #   password is different
_DB_PORT = os.getenv("DB_PORT", "3306")
_DB_NAME = os.getenv("DB_NAME", "quizdatabase")

# Full URL can still override everything via DATABASE_URL env var
_DEFAULT_URL = f"mysql+pymysql://{_DB_USER}:{_DB_PASS}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", _DEFAULT_URL)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping":  True,   # auto-reconnect on dropped connections
        "pool_recycle":   1800,   # recycle connections every 30 min
        "pool_size":      5,
        "max_overflow":   10,
        "connect_args":   {
            "connect_timeout": 10,    # fail fast if MySQL is down
            "read_timeout":    30,
            "write_timeout":   30,
        },
    }

    JWT_SECRET_KEY           = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")))

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB banner uploads