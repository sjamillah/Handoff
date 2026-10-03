"""Health check endpoint."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine

router = APIRouter(tags=["health"])


@router.get("/health", responses={503: {"description": "The database is unreachable."}})
def health() -> JSONResponse:
    """Report whether the API can reach the database. Does not require authentication.

    Returns 200 when ``SELECT 1`` succeeds and 503 when it fails. The response
    never includes the error, which could reveal connection details.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return JSONResponse(status_code=200, content={"status": "ok", "database": "up"})
