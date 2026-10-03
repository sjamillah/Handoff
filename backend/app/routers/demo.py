"""Endpoints for checking role rules manually. To be removed before submission."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import require_roles
from app.models import User
from app.schemas import ErrorOut

router = APIRouter(
    prefix="/demo",
    tags=["demo"],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}},
)


@router.get("/client")
def client_only(user: Annotated[User, Depends(require_roles("client"))]) -> dict[str, str]:
    """Return a greeting for clients only."""
    return {"message": f"Hello {user.email}, you are a client"}


@router.get("/operator")
def operator_only(
    user: Annotated[User, Depends(require_roles("operator", "admin"))],
) -> dict[str, str]:
    """Return a greeting for operators and admins."""
    return {"message": f"Hello {user.email}, you have operator access"}


@router.get("/admin")
def admin_only(user: Annotated[User, Depends(require_roles("admin"))]) -> dict[str, str]:
    """Return a greeting for admins only."""
    return {"message": f"Hello {user.email}, you are an admin"}
