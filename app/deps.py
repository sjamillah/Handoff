"""FastAPI dependencies for database sessions, authentication and role checks."""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User


def get_db() -> Iterator[Session]:
    """Yield a database session for one request and close it afterwards."""
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    """Return the active user that owns the session cookie.

    The user is loaded from the database on every request, so deactivation
    and role changes apply to existing sessions immediately.

    Raises:
        HTTPException: 401 if there is no session, or the user does not exist
            or is inactive. The session is cleared.
    """
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[[User], User]:
    """Create a dependency that allows only the given roles.

    Roles are listed explicitly instead of ranked, because client permissions
    are not a subset of operator permissions.

    Args:
        *roles: Allowed roles.

    Returns:
        A dependency that returns the current user, or raises HTTPException
        403 for any other role.

    Example:
        ``Depends(require_roles("operator", "admin"))``
    """

    def check_role(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Not allowed")
        return user

    return check_role
