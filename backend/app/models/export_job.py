"""Export job model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.constants import EXPORT_STATUSES, sql_in


class ExportJob(Base):
    """Simulated export of one assigned episode, processed by the worker.

    One job per assignment, created in the same transaction as the assignment.
    A worker claims a due job, holds it with a lease (``locked_until``) while it
    works outside any transaction, and then records the outcome.

    ``attempts`` counts attempts started, so a job that crashes its worker still
    runs out of attempts instead of retrying forever. ``max_attempts`` is copied
    from configuration when the job is created, so changing the setting later
    does not change jobs already queued.

    The two partial indexes cover only the rows a worker looks for: pending jobs
    that are due, and running jobs whose lease may have expired. Finished jobs,
    which accumulate, are not in either index.
    """

    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint(sql_in("status", EXPORT_STATUSES), name="status_valid"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        CheckConstraint("attempts BETWEEN 0 AND max_attempts", name="attempts_in_range"),
        CheckConstraint(
            "(status = 'running') = (locked_until IS NOT NULL)", name="lease_only_while_running"
        ),
        Index("ix_export_jobs_due", "next_run_at", postgresql_where=text("status = 'pending'")),
        Index("ix_export_jobs_lease", "locked_until", postgresql_where=text("status = 'running'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    attempts: Mapped[int] = mapped_column(server_default="0")
    max_attempts: Mapped[int]
    last_error: Mapped[str | None] = mapped_column(Text)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
