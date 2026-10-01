from fastapi import APIRouter, HTTPException, Request

from app.deps import DbSession
from app.schemas import LoginIn, UserOut
from app.services.users import authenticate

public_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])


@public_router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, db: DbSession):
    user = authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()
