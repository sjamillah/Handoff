"""User model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.constants import ROLES, sql_in
from app.models.organisation import Organisation


class User(Base):
    """Account that can log in, with the role client, operator or admin.

    The ``client_has_organisation`` constraint requires an organisation for
    clients and forbids one for operators and admins. Users are deactivated
    rather than deleted, so records that reference them remain valid.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(sql_in("role", ROLES), name="role_valid"),
        CheckConstraint(
            "(role = 'client') = (organisation_id IS NOT NULL)",
            name="client_has_organisation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisations.id"))
    is_active: Mapped[bool] = mapped_column(server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organisation: Mapped[Organisation | None] = relationship()

    @property
    def organisation_name(self) -> str | None:
        """Name of the user's organisation, or None for operators and admins."""
        return self.organisation.name if self.organisation else None
