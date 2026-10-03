"""Dataset request model."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db import Base
from app.models.assignment import Assignment
from app.models.constants import REQUEST_STATUSES, sql_in

if TYPE_CHECKING:
    from app.models.status_history import StatusHistory


class DatasetRequest(Base):
    """Client request for a number of episodes of one task.

    Named ``DatasetRequest`` to avoid a clash with ``fastapi.Request``. The
    database restricts ``status`` to known values. Allowed transitions between
    statuses are enforced in the service layer.
    """

    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(sql_in("status", REQUEST_STATUSES), name="status_valid"),
        CheckConstraint("episodes_requested > 0", name="episodes_requested_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_name: Mapped[str] = mapped_column(String(200))
    episodes_requested: Mapped[int]
    deadline: Mapped[date]
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    history: Mapped[list["StatusHistory"]] = relationship(order_by="StatusHistory.id")

    assigned_count: Mapped[int] = column_property(
        select(func.count(Assignment.id))
        .where(Assignment.request_id == id)
        .correlate_except(Assignment)
        .scalar_subquery()
    )
