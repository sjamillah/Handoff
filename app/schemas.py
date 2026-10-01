from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Role = Literal["client", "operator", "admin"]


def check_client_organisation(role, organisation):
    if role == "client" and not organisation:
        raise ValueError("a client must have an organisation")
    if role != "client" and organisation:
        raise ValueError("only clients can have an organisation")


class LoginIn(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role
    organisation: str | None = None

    @model_validator(mode="after")
    def organisation_matches_role(self):
        check_client_organisation(self.role, self.organisation)
        return self


class RoleChange(BaseModel):
    role: Role
    organisation: str | None = None

    @model_validator(mode="after")
    def organisation_matches_role(self):
        check_client_organisation(self.role, self.organisation)
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    organisation_name: str | None
    is_active: bool
