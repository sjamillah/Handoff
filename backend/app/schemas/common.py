"""Types shared by several schema modules, and the error body."""

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["client", "operator", "admin"]
RequestStatus = Literal["submitted", "in_progress", "delivered", "accepted", "rejected"]
Quality = Literal["good", "usable", "bad"]


class ErrorOut(BaseModel):
    """Error response body."""

    detail: str = Field(examples=["Not allowed"])
