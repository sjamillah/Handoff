"""Pydantic request and response models. Descriptions and examples appear in Swagger and ReDoc."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Role = Literal["client", "operator", "admin"]


class ErrorOut(BaseModel):
    """Error response body."""

    detail: str = Field(examples=["Not allowed"])


class LoginIn(BaseModel):
    """Login credentials. The email is matched case-insensitively."""

    email: str = Field(examples=["client-a@example.com"])
    password: str = Field(examples=["client123"])


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
    password: str = Field(min_length=8, max_length=128, examples=["a-long-password"])


class RoleChange(RoleWithOrganisation):
    """Body for changing a user's role. A non-client role clears the organisation."""


class UserOut(BaseModel):
    """User as returned by the API. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[4])
    email: str = Field(examples=["client-a@example.com"])
    role: Role = Field(examples=["client"])
    organisation_name: str | None = Field(examples=["Acme Robotics"])
    is_active: bool = Field(examples=[True])


ImportOutcome = Literal["duplicate", "conflict", "rejected"]


class ImportRowResult(BaseModel):
    """Outcome of one CSV row that was not imported."""

    line: int = Field(
        description="Line number in the file, counting the header as 1.", examples=[59]
    )
    episode_id: str | None = Field(examples=["EP-00011"])
    outcome: ImportOutcome = Field(examples=["conflict"])
    reason: str = Field(examples=["differs from line 3: quality 'good' vs 'bad'"])


class ImportReport(BaseModel):
    """Result of an episode import: counts per outcome and every row not imported."""

    imported: int = 0
    duplicates: int = 0
    conflicts: int = 0
    rejected: int = 0
    rows: list[ImportRowResult] = Field(default_factory=list)

    def add(self, outcome: ImportOutcome, line: int, episode_id: str | None, reason: str) -> None:
        """Record a row that was not imported and increase the count for its outcome."""
        self.rows.append(
            ImportRowResult(line=line, episode_id=episode_id, outcome=outcome, reason=reason)
        )
        if outcome == "duplicate":
            self.duplicates += 1
        elif outcome == "conflict":
            self.conflicts += 1
        else:
            self.rejected += 1
