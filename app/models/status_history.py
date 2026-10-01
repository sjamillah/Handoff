from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.constants import REQUEST_STATUSES, sql_in


class StatusHistory(Base):
    __tablename__ = "status_history"
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR {sql_in('from_status', REQUEST_STATUSES)}",
            name="from_status_valid",
        ),
        CheckConstraint(sql_in("to_status", REQUEST_STATUSES), name="to_status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
