"""Adds the demo organisations and users. Running it again changes nothing."""

import os

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Organisation, User
from app.security import hash_password

ORGANISATIONS = ["Acme Robotics", "Beta Labs"]

USERS = [
    ("admin@example.com", "SEED_ADMIN_PASSWORD", "admin", None),
    ("ops1@example.com", "SEED_OPERATOR_PASSWORD", "operator", None),
    ("ops2@example.com", "SEED_OPERATOR_PASSWORD", "operator", None),
    ("client-a@example.com", "SEED_CLIENT_PASSWORD", "client", "Acme Robotics"),
    ("client-b@example.com", "SEED_CLIENT_PASSWORD", "client", "Beta Labs"),
]


def seed(session):
    for name in ORGANISATIONS:
        session.execute(
            insert(Organisation).values(name=name).on_conflict_do_nothing(index_elements=["name"])
        )
    org_ids = dict(session.execute(select(Organisation.name, Organisation.id)).all())

    created = 0
    for email, password_var, role, org_name in USERS:
        result = session.execute(
            insert(User)
            .values(
                email=email,
                password_hash=hash_password(os.environ[password_var]),
                role=role,
                organisation_id=org_ids[org_name] if org_name else None,
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
