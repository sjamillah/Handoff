"""Assignment model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Assignment(Base):
    """Assignment of one episode to one request.

    The UNIQUE constraint on ``episode_id`` guarantees that an episode belongs
    to at most one request at a time, including under concurrent writes.
    ``episode_id`` references ``episodes.id``, not the CSV identifier.
    """

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id"), unique=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
