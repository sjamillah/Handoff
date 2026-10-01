"""Application settings loaded from environment variables.

Attributes:
    DATABASE_URL: SQLAlchemy URL of the PostgreSQL database. Required.
    SESSION_SECRET: Key that signs session cookies. When unset, a random key is
        generated at startup, which invalidates all sessions on restart.
    SESSION_HTTPS_ONLY: Restricts the session cookie to HTTPS when true.
    SESSION_MAX_AGE_SECONDS: Lifetime of a session in seconds.
"""

import os
import secrets

DATABASE_URL = os.environ["DATABASE_URL"]

SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)
SESSION_HTTPS_ONLY = os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
