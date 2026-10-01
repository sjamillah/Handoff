from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.deps import get_current_user
from app.routers import admin, auth, demo, health
from app.services.errors import ConflictError, NotFoundError, RuleError

app = FastAPI(title="Dataset Request Desk")

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=config.SESSION_HTTPS_ONLY,
)

app.include_router(health.router)
app.include_router(auth.public_router)

for router in (auth.router, admin.router, demo.router):
    app.include_router(router, dependencies=[Depends(get_current_user)])


def error_handler(status_code):
    def handle(request, exc):
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


app.add_exception_handler(NotFoundError, error_handler(404))
app.add_exception_handler(ConflictError, error_handler(409))
app.add_exception_handler(RuleError, error_handler(400))
