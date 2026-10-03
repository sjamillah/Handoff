"""Login and user management bodies."""

from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.common import Role


class LoginIn(BaseModel):
    """Login credentials. The email is matched case-insensitively.

    Both fields are capped so that an oversized password is refused before it
    reaches the deliberately slow password hash.
    """

    email: str = Field(max_length=255, examples=["user@example.com"])
    password: str = Field(max_length=128, examples=["your-password"])


class RoleWithOrganisation(BaseModel):
    """Role and, for clients, the organisation name.

    Shared by ``UserCreate`` and ``RoleChange``. Mirrors the
    ``client_has_organisation`` database constraint, so invalid input is
    rejected with a 422 before it reaches the database.
    """

    role: Role = Field(examples=["client"])
    organisation: str | None = Field(
        default=None,
        description=(
            "Name of an existing organisation. Required for clients, not allowed for other roles."
        ),
        examples=["Acme Robotics"],
    )

    @model_validator(mode="after")
    def organisation_matches_role(self) -> Self:
        """Require an organisation for clients and reject one for other roles."""
        if self.role == "client" and not self.organisation:
            raise ValueError("a client must have an organisation")
        if self.role != "client" and self.organisation:
            raise ValueError("only clients can have an organisation")
        return self


class UserCreate(RoleWithOrganisation):
    """Body for creating a user."""

    email: EmailStr = Field(examples=["new.client@example.com"])
    name: str = Field(min_length=1, max_length=200, examples=["Nadia Client"])
    password: str = Field(min_length=8, max_length=128, examples=["a-long-password"])


class RoleChange(RoleWithOrganisation):
    """Body for changing a user's role. A non-client role clears the organisation."""


class UserOut(BaseModel):
    """User as returned by the API. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[4])
    email: str = Field(examples=["user@example.com"])
    name: str = Field(examples=["Acme Robotics"])
    role: Role = Field(examples=["client"])
    organisation_name: str | None = Field(examples=["Acme Robotics"])
    is_active: bool = Field(examples=[True])
