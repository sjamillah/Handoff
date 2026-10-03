"""Episode listing and assignment bodies."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.normalise import normalise_episode_id
from app.schemas.common import Quality


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
        cleaned = [normalise_episode_id(value) for value in values]
        if any(not value for value in cleaned):
            raise ValueError("episode_ids contains a blank id")
        return list(dict.fromkeys(cleaned))


class AssignmentOut(BaseModel):
    """Result of an assignment: the episodes added and the request's new total."""

    request_id: int = Field(examples=[1])
    assigned: list[str] = Field(examples=[["EP-00001", "EP-00002"]])
    assigned_count: int = Field(examples=[12])
    episodes_requested: int = Field(examples=[50])
