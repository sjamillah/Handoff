"""Episode model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.constants import KNOWN_ROBOTS, QUALITIES, sql_in


class Episode(Base):
    """Recorded robot episode, imported from the CSV export.

    ``episode_id`` is the identifier from the CSV. It is unique, which makes
    repeated imports idempotent. ``recorded_at`` and (``task_name``,
    ``quality``) are indexed for the analytics queries.
    """

    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint(sql_in("quality", QUALITIES), name="quality_valid"),
        CheckConstraint(sql_in("robot_id", KNOWN_ROBOTS), name="robot_known"),
        CheckConstraint("duration_seconds > 0", name="duration_positive"),
        Index("ix_episodes_task_name_quality", "task_name", "quality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(100), unique=True)
    robot_id: Mapped[str] = mapped_column(String(50))
    task_name: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[int]
    operator_name: Mapped[str] = mapped_column(String(200))
    quality: Mapped[str] = mapped_column(String(10))
