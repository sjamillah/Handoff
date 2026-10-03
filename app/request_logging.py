"""One JSON log line per HTTP request.

Each line has the method, path, status code, duration in milliseconds and the
id of the authenticated user, or null. Query strings, headers, cookies and
bodies are never logged, so passwords and session cookies cannot leak into
the logs.

The user id comes from ``request.state.user_id``. ``get_current_user`` sets it
after it has validated the session, and login sets it after a successful
login. The middleware reads it once the route has run, so it logs a user only
when the request was really authenticated, never a value decoded from an
unchecked cookie.
"""

import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import Request, Response

logger = logging.getLogger("handoff.requests")


class JsonFormatter(logging.Formatter):
    """Format a record as a single JSON object with a UTC timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record's fields as one line of JSON."""
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            **getattr(record, "fields", {}),
        }
        return json.dumps(entry)


def configure_logging() -> None:
    """Send request logs to stdout as JSON, once, without passing them to other handlers."""
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Time the request, then log one line with its outcome and user.

    An unhandled exception is logged with status 500 and raised again.
    """
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        fields = {
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "user_id": getattr(request.state, "user_id", None),
        }
        logger.info("request", extra={"fields": fields})
