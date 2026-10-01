"""Throwaway routes for checking the role rules by hand. Delete before submitting."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import require_roles
from app.models import User

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/client")
def client_only(user: Annotated[User, Depends(require_roles("client"))]):
    return {"message": f"Hello {user.email}, you are a client"}


@router.get("/operator")
def operator_only(user: Annotated[User, Depends(require_roles("operator", "admin"))]):
    return {"message": f"Hello {user.email}, you have operator access"}


@router.get("/admin")
def admin_only(user: Annotated[User, Depends(require_roles("admin"))]):
    return {"message": f"Hello {user.email}, you are an admin"}
