import os
import secrets

DATABASE_URL = os.environ["DATABASE_URL"]

SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)
SESSION_HTTPS_ONLY = os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
