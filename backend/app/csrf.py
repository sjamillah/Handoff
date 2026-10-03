"""CSRF protection for the cookie session.

Three layers protect state-changing requests:

1. The session cookie is ``SameSite=Lax``, so browsers do not attach it to
   cross-site POST, PUT or DELETE requests.
2. The API only accepts JSON bodies (and multipart for the CSV upload). A
   cross-site page cannot send ``application/json`` without a CORS preflight,
   and the API never approves one.
3. This middleware refuses any unsafe request whose ``Origin`` header names a
   site outside ``ALLOWED_ORIGINS``. Browsers always send ``Origin`` on these
   requests. Clients without one, such as curl or the test client, are not
   browsers and cannot carry a victim's cookie, so they are let through.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app import config

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


async def check_origin(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Refuse a state-changing request sent from another site, with 403."""
    origin = request.headers.get("origin")
    if request.method in UNSAFE_METHODS and origin and origin not in config.ALLOWED_ORIGINS:
        return JSONResponse(status_code=403, content={"detail": "Cross-site request refused"})
    return await call_next(request)
