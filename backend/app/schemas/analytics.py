"""Analytics response."""

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import RequestStatus


class DailyRobotCount(BaseModel):
    """Episodes recorded by one robot on one day."""

    day: date
    robot_id: str = Field(examples=["arm-01"])
    episodes: int = Field(examples=[14])


class StatusCount(BaseModel):
    """Number of requests currently in one status."""

    status: RequestStatus = Field(examples=["in_progress"])
    requests: int = Field(examples=[3])


class TaskCount(BaseModel):
    """Number of good episodes for one task name."""

    task_name: str = Field(examples=["pick cup"])
    good_episodes: int = Field(examples=[19])


class AnalyticsOut(BaseModel):
    """Analytics for a range of days in the business time zone."""

    date_from: date
    date_to: date
    timezone: str = Field(examples=["Africa/Kigali"])
    episodes_per_day: list[DailyRobotCount] = Field(
        description="Episodes per day and robot, by recorded_at. Days with no episodes are omitted."
    )
    requests_by_status: list[StatusCount] = Field(
        description="Current status of the requests submitted in the range, every status listed."
    )
    median_seconds_submitted_to_delivered: float | None = Field(
        description=(
            "Median time from submission to first delivery, for requests first delivered "
            "in the range. Null when none were."
        ),
        examples=[93600.0],
    )
    delivered_requests_measured: int = Field(
        description="Number of requests the median is based on.", examples=[7]
    )
    top_tasks_by_good_episodes: list[TaskCount] = Field(
        description="Up to five task names, most good episodes recorded in the range first."
    )
