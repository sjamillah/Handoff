"""User management endpoints for admins.

The admin role check applies to the whole router, so every endpoint added
here is admin-only.
"""

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_roles
from app.models import User
from app.schemas import ErrorOut, RoleChange, UserCreate, UserOut
from app.services import users

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("admin"))],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}},
)


@router.get("/users", response_model=list[UserOut])
def list_users(db: DbSession) -> list[User]:
    """List every user, active ones first."""
    return users.list_users(db)


@router.get("/organisations", response_model=list[str])
def list_organisations(db: DbSession) -> list[str]:
    """Names of the organisations a client can belong to."""
    return users.list_organisation_names(db)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=201,
    responses={400: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def create_user(body: UserCreate, db: DbSession) -> User:
    """Create a user. Clients require an existing organisation."""
    return users.create_user(db, body)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserOut,
    responses={400: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)
def deactivate_user(user_id: int, db: DbSession, admin: CurrentUser) -> User:
    """Deactivate a user. Their session ends on their next request.

    Admins cannot deactivate their own account.
    """
    return users.deactivate_user(db, user_id, admin)


@router.put(
    "/users/{user_id}/role",
    response_model=UserOut,
    responses={400: {"model": ErrorOut}, 404: {"model": ErrorOut}},
)
def change_role(user_id: int, body: RoleChange, db: DbSession, admin: CurrentUser) -> User:
    """Change a user's role. The change applies on their next request.

    Admins cannot change their own role.
    """
    return users.change_role(db, user_id, body, admin)
