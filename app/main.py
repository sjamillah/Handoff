"""FastAPI application: session middleware, routers and error handlers.

Only the health and login routers are public. All other routers are
included with ``get_current_user``, so new routes require authentication
by default.
"""

from collections.abc import Callable

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.deps import get_current_user
from app.routers import admin, auth, demo, episodes, health, requests
from app.services.errors import ConflictError, NotFoundError, PermissionDeniedError, RuleError

DESCRIPTION = """
Handoff is the Dataset Request Desk: an internal API for requesting and delivering
datasets of recorded robot episodes.

Authentication uses a session cookie, set by `POST /auth/login`. Browsers send
the cookie automatically on later requests, including requests made from this page.
"""

app = FastAPI(title="Handoff", version="0.1.0", description=DESCRIPTION)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=config.SESSION_HTTPS_ONLY,
)

app.include_router(health.router)
app.include_router(auth.public_router)

for router in (auth.router, admin.router, episodes.router, requests.router, demo.router):
    app.include_router(router, dependencies=[Depends(get_current_user)])


def error_handler(status_code: int) -> Callable[[Request, Exception], JSONResponse]:
    """Create an exception handler that returns the exception message.

    Args:
        status_code: HTTP status code of the response.

    Returns:
        A handler that responds with ``{"detail": <message>}``.
    """

    def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


app.add_exception_handler(NotFoundError, error_handler(404))
app.add_exception_handler(PermissionDeniedError, error_handler(403))
app.add_exception_handler(ConflictError, error_handler(409))
app.add_exception_handler(RuleError, error_handler(400))
