"""Status history model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.constants import REQUEST_STATUSES, ROLES, sql_in
from app.models.user import User


class StatusHistory(Base):
    """Record of one status change on a request, with the user, their role and the time.

    ``changed_by_role`` is the role at the time of the change, so the record
    stays accurate if the user's role changes later.
    ``from_status`` is NULL on the first row, written when the request is
    created. These rows are the source for time from submitted to delivered.
    """

    __tablename__ = "status_history"
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR {sql_in('from_status', REQUEST_STATUSES)}",
            name="from_status_valid",
        ),
        CheckConstraint(sql_in("to_status", REQUEST_STATUSES), name="to_status_valid"),
        CheckConstraint(sql_in("changed_by_role", ROLES), name="changed_by_role_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_by_role: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    changed_by: Mapped[User] = relationship()
