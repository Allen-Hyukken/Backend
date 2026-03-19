import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

    # MySQL — change user/password/host to match your setup
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:12345@localhost:3306/quizdatabase"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # auto-reconnect on dropped connections
        "pool_recycle":  3600,
        "pool_size":     10,
        "max_overflow":  20,
    }

    # JWT
    JWT_SECRET_KEY           = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_EXPIRATION_HOURS", 24)))

    # Max upload: 16 MB (classroom banners)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
