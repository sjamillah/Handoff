"""Dataset request bodies and the status history entry."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import config
from app.normalise import normalise_task_name
from app.schemas.common import RequestStatus, Role


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
        value = normalise_task_name(value)
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
    client_name: str = Field(examples=["Acme Robotics"])
    task_name: str = Field(examples=["pick cup"])
    episodes_requested: int = Field(examples=[50])
    deadline: date
    notes: str | None = Field(examples=["Daylight recordings only."])
    status: RequestStatus = Field(examples=["submitted"])
    assigned_count: int = Field(description="Episodes assigned so far.", examples=[12])
    available_transitions: list[RequestStatus] = Field(
        description="Statuses the current user may move this request to now.",
        examples=[["delivered"]],
    )
    can_assign: bool = Field(
        description="Whether the current user may assign episodes to this request now.",
        examples=[True],
    )
    created_at: datetime


class RequestDetail(RequestOut):
    """Dataset request with its full status history, oldest first."""

    history: list[StatusChangeOut]
