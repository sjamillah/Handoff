"""Episode model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.constants import KNOWN_ROBOTS, QUALITIES, sql_in


class Episode(Base):
    """Recorded robot episode, imported from the CSV export.

    ``episode_id`` is the identifier from the CSV. It is unique, which makes
    repeated imports idempotent.

    Indexes:
        (recorded_at, robot_id): episodes per day per robot, answered from the
            index alone. Also serves any filter on recorded_at.
        (recorded_at, task_name) for good episodes only: top tasks by good
            episodes, without reading usable or bad rows.
        (task_name, quality): the operator episode list filters.
    """

    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint(sql_in("quality", QUALITIES), name="quality_valid"),
        CheckConstraint(sql_in("robot_id", KNOWN_ROBOTS), name="robot_known"),
        CheckConstraint("duration_seconds > 0", name="duration_positive"),
        Index("ix_episodes_task_name_quality", "task_name", "quality"),
        Index("ix_episodes_recorded_at_robot_id", "recorded_at", "robot_id"),
        Index(
            "ix_episodes_good_recorded_at_task_name",
            "recorded_at",
            "task_name",
            postgresql_where=text("quality = 'good'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(100), unique=True)
    robot_id: Mapped[str] = mapped_column(String(50))
    task_name: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int]
    operator_name: Mapped[str] = mapped_column(String(200))
    quality: Mapped[str] = mapped_column(String(10))
