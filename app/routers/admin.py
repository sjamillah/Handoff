from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_roles
from app.schemas import RoleChange, UserCreate, UserOut
from app.services import users

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("admin"))]
)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DbSession):
    return users.create_user(db, body)


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: DbSession, admin: CurrentUser):
    return users.deactivate_user(db, user_id, admin)


@router.put("/users/{user_id}/role", response_model=UserOut)
def change_role(user_id: int, body: RoleChange, db: DbSession, admin: CurrentUser):
    return users.change_role(db, user_id, body, admin)
