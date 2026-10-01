"""Login and logout endpoints.

``public_router`` holds login, the only public endpoint. ``router`` is
included with authentication, like every other router.
"""

from fastapi import APIRouter, HTTPException, Request

from app.deps import DbSession
from app.models import User
from app.schemas import ErrorOut, LoginIn, UserOut
from app.services.users import authenticate

public_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"], responses={401: {"model": ErrorOut}})


@public_router.post("/login", response_model=UserOut, responses={401: {"model": ErrorOut}})
def login(body: LoginIn, request: Request, db: DbSession) -> User:
    """Log in and set the session cookie.

    Unknown email, wrong password and deactivated account all return the same
    401 response.
    """
    user = authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    """Log out by clearing the session cookie."""
    request.session.clear()
