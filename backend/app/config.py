"""Application settings loaded from environment variables.

Attributes:
    DATABASE_URL: SQLAlchemy URL of the PostgreSQL database. Required.
    SESSION_SECRET: Key that signs session cookies. When unset, a random key is
        generated at startup, which invalidates all sessions on restart.
    SESSION_HTTPS_ONLY: Restricts the session cookie to HTTPS when true.
    SESSION_MAX_AGE_SECONDS: Lifetime of a session in seconds.
    ALLOWED_ORIGINS: Origins allowed to send state-changing requests, comma
        separated. Requests from any other Origin are refused (CSRF protection).
    APP_TIMEZONE: Time zone of the business, used to decide what "today" is for
        deadlines. Defaults to Africa/Kigali.
"""

import os
import secrets
from zoneinfo import ZoneInfo

DATABASE_URL = os.environ["DATABASE_URL"]

SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)
SESSION_HTTPS_ONLY = os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60

APP_TIMEZONE = ZoneInfo(os.environ.get("APP_TIMEZONE", "Africa/Kigali"))

ALLOWED_ORIGINS = frozenset(
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
)
