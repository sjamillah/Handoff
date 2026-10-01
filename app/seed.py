"""Seed the demo organisations and users defined in the brief.

Run with ``python -m app.seed``. Existing rows are skipped and never
updated, so the script is safe to run on every start and does not
overwrite later changes made by an admin.
"""

import os
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Organisation, User
from app.security import hash_password


class SeedUser(NamedTuple):
    """Demo user definition. The password is read from ``password_env_var``."""

    email: str
    password_env_var: str
    role: str
    organisation: str | None


ORGANISATIONS = ["Acme Robotics", "Beta Labs"]

USERS = [
    SeedUser("admin@example.com", "SEED_ADMIN_PASSWORD", "admin", None),
    SeedUser("ops1@example.com", "SEED_OPERATOR_PASSWORD", "operator", None),
    SeedUser("ops2@example.com", "SEED_OPERATOR_PASSWORD", "operator", None),
    SeedUser("client-a@example.com", "SEED_CLIENT_PASSWORD", "client", "Acme Robotics"),
    SeedUser("client-b@example.com", "SEED_CLIENT_PASSWORD", "client", "Beta Labs"),
]


def seed(session: Session) -> int:
    """Insert missing organisations and users.

    Uses ``INSERT ... ON CONFLICT DO NOTHING``, so existing rows are skipped
    atomically.

    Args:
        session: Database session.

    Returns:
        Number of users created.
    """
    for name in ORGANISATIONS:
        session.execute(
            insert(Organisation).values(name=name).on_conflict_do_nothing(index_elements=["name"])
        )
    org_ids = dict(session.execute(select(Organisation.name, Organisation.id)).all())

    created = 0
    for user in USERS:
        result = session.execute(
            insert(User)
            .values(
                email=user.email,
                password_hash=hash_password(os.environ[user.password_env_var]),
                role=user.role,
                organisation_id=org_ids[user.organisation] if user.organisation else None,
            )
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(User.id)
        )
        created += len(result.all())
    session.commit()
    return created


if __name__ == "__main__":
    with SessionLocal() as session:
        created = seed(session)
    print(f"seed: {created} users created, {len(USERS) - created} already existed")
