from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
