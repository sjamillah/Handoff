"""Pydantic request and response models. Descriptions and examples appear in Swagger and ReDoc."""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app import config

Role = Literal["client", "operator", "admin"]
RequestStatus = Literal["submitted", "in_progress", "delivered", "accepted", "rejected"]


class ErrorOut(BaseModel):
    """Error response body."""

    detail: str = Field(examples=["Not allowed"])


class LoginIn(BaseModel):
    """Login credentials. The email is matched case-insensitively."""

    email: str = Field(examples=["user@example.com"])
    password: str = Field(examples=["your-password"])


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


class RequestCreate(BaseModel):
    """Body for creating a dataset request."""

    task_name: str = Field(
        min_length=1,
        max_length=200,
        description="Task to collect. Stored trimmed and lower-cased, like imported episodes.",
        examples=["pick cup"],
    )
    episodes_requested: int = Field(gt=0, le=100_000, examples=[50])
    deadline: date = Field(
        description="Delivery date. Today or later, in the business time zone (APP_TIMEZONE).",
        examples=["2026-12-01"],
    )
    notes: str | None = Field(default=None, max_length=2000, examples=["Daylight recordings only."])

    @field_validator("task_name")
    @classmethod
    def normalise_task_name(cls, value: str) -> str:
        """Trim and lower-case the task name and reject one that is only whitespace."""
        value = value.strip().lower()
        if not value:
            raise ValueError("task_name is blank")
        return value

    @field_validator("deadline")
    @classmethod
    def deadline_not_in_past(cls, value: date) -> date:
        """Reject a deadline before today's date in the business time zone.

        Using UTC would reject a same-day deadline between midnight and 02:00
        in Kigali, where the business runs.
        """
        if value < datetime.now(config.APP_TIMEZONE).date():
            raise ValueError("deadline is in the past")
        return value

    @field_validator("notes")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        """Trim notes and store empty notes as None."""
        value = value.strip() if value else None
        return value or None


class StatusChangeIn(BaseModel):
    """Body for moving a request to another status."""

    to_status: RequestStatus = Field(examples=["in_progress"])


class StatusChangeOut(BaseModel):
    """One entry in a request's status history.

    Clients see who made a change only by role, apart from their own changes.
    Staff names and internal user ids are never shown to clients.
    """

    from_status: RequestStatus | None = Field(examples=["submitted"])
    to_status: RequestStatus = Field(examples=["in_progress"])
    changed_by_role: Role = Field(
        description="Role of the user at the time of the change.", examples=["operator"]
    )
    changed_by_name: str | None = Field(
        description="Name of the user. Null for clients viewing a change made by staff.",
        examples=["Olu Operator"],
    )
    changed_at: datetime


class RequestOut(BaseModel):
    """Dataset request as returned in lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    client_id: int = Field(examples=[4])
    task_name: str = Field(examples=["pick cup"])
    episodes_requested: int = Field(examples=[50])
    deadline: date
    notes: str | None = Field(examples=["Daylight recordings only."])
    status: RequestStatus = Field(examples=["submitted"])
    assigned_count: int = Field(description="Episodes assigned so far.", examples=[12])
    created_at: datetime


class RequestDetail(RequestOut):
    """Dataset request with its full status history, oldest first."""

    history: list[StatusChangeOut]


Quality = Literal["good", "usable", "bad"]


class EpisodeOut(BaseModel):
    """Episode as listed for operators, with the request it is assigned to, if any."""

    episode_id: str = Field(examples=["EP-00001"])
    robot_id: str = Field(examples=["arm-01"])
    task_name: str = Field(examples=["pick cup"])
    recorded_at: datetime
    duration_seconds: int = Field(examples=[42])
    operator_name: str = Field(examples=["Diane"])
    quality: Quality = Field(examples=["good"])
    assigned_request_id: int | None = Field(examples=[None])


class EpisodePage(BaseModel):
    """One page of episodes and the total number that match the filters."""

    items: list[EpisodeOut]
    total: int = Field(examples=[171])
    limit: int = Field(examples=[50])
    offset: int = Field(examples=[0])


class AssignmentIn(BaseModel):
    """Episodes to assign to a request, by their CSV episode_id."""

    episode_ids: list[str] = Field(
        min_length=1, max_length=500, examples=[["EP-00001", "EP-00002"]]
    )

    @field_validator("episode_ids")
    @classmethod
    def normalise_ids(cls, values: list[str]) -> list[str]:
        """Trim and upper-case ids like the import does, and drop repeats while keeping order."""
        cleaned = [value.strip().upper() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("episode_ids contains a blank id")
        return list(dict.fromkeys(cleaned))


class AssignmentOut(BaseModel):
    """Result of an assignment: the episodes added and the request's new total."""

    request_id: int = Field(examples=[1])
    assigned: list[str] = Field(examples=[["EP-00001", "EP-00002"]])
    assigned_count: int = Field(examples=[12])
    episodes_requested: int = Field(examples=[50])
