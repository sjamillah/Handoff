"""Export status bodies."""

from typing import Literal

from pydantic import BaseModel, Field

ExportStatus = Literal["pending", "running", "succeeded", "failed"]


class ExportJobOut(BaseModel):
    """Export status of one assigned episode."""

    episode_id: str = Field(examples=["EP-00010"])
    status: ExportStatus = Field(examples=["running"])
    attempts: int = Field(description="Attempts started so far.", examples=[2])
    max_attempts: int = Field(examples=[5])
    last_error: str | None = Field(
        description="Error of the latest failed attempt.", examples=["Simulated export failure"]
    )


class ExportListOut(BaseModel):
    """Export status of every episode assigned to a request."""

    jobs: list[ExportJobOut]
    finished: bool = Field(
        description="True when every export has succeeded or failed, so polling can stop.",
        examples=[False],
    )
