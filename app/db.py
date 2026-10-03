"""Database engine, session factory and declarative base.

Connections use the UTC time zone, so timestamps are returned in UTC
regardless of the server configuration. A connection attempt gives up after
5 seconds, so the health check reports a lost database instead of hanging.
"""

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(column_0_label)s",
}


class Base(DeclarativeBase):
    """Declarative base for all models.

    Applies a naming convention that gives every constraint a deterministic
    name, for example ``ck_users_role_valid``.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(
    DATABASE_URL, connect_args={"options": "-c timezone=utc", "connect_timeout": 5}
)
SessionLocal = sessionmaker(bind=engine)
