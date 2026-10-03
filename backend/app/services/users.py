"""User authentication and account management."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Organisation, User
from app.schemas import RoleChange, UserCreate
from app.security import DUMMY_HASH, hash_password, normalise_email, verify_password
from app.services.errors import ConflictError, NotFoundError, RuleError, violated_constraint

EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user for valid credentials, or None.

    Unknown emails, wrong passwords and inactive accounts all return None.
    For an unknown email the password is verified against ``DUMMY_HASH``, so
    the response time does not reveal whether the email exists.

    Args:
        db: Database session.
        email: Email as entered. Normalised before lookup.
        password: Plain-text password.

    Returns:
        The authenticated user, or None.
    """
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    password_ok = verify_password(user.password_hash if user else DUMMY_HASH, password)
    if user and user.is_active and password_ok:
        return user
    return None


def find_organisation_id(db: Session, name: str | None) -> int | None:
    """Return the id of the organisation with the given name.

    Args:
        db: Database session.
        name: Organisation name, or None for operators and admins.

    Returns:
        The organisation id, or None if ``name`` is None.

    Raises:
        RuleError: No organisation has this name.
    """
    if name is None:
        return None
    organisation_id = db.scalar(select(Organisation.id).where(Organisation.name == name))
    if organisation_id is None:
        raise RuleError(f"Unknown organisation: {name}")
    return organisation_id


def get_user(db: Session, user_id: int) -> User:
    """Return the user with the given id.

    Raises:
        NotFoundError: No user has this id.
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def create_user(db: Session, data: UserCreate) -> User:
    """Create a user with a hashed password.

    Duplicate emails are detected through the ``uq_users_email`` constraint
    instead of a prior lookup, which would let two concurrent requests both
    succeed.

    Raises:
        RuleError: The organisation does not exist.
        ConflictError: A user with this email already exists.
    """
    user = User(
        email=normalise_email(data.email),
        name=data.name.strip(),
        password_hash=hash_password(data.password),
        role=data.role,
        organisation_id=find_organisation_id(db, data.organisation),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if violated_constraint(exc) == EMAIL_UNIQUE_CONSTRAINT:
            raise ConflictError("A user with this email already exists") from exc
        raise
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int, acting_user: User) -> User:
    """Deactivate a user. Their existing sessions end on the next request.

    Args:
        db: Database session.
        user_id: Id of the user to deactivate.
        acting_user: Admin performing the change.

    Raises:
        NotFoundError: No user has this id.
        RuleError: The admin targeted their own account.
    """
    user = get_user(db, user_id)
    if user.id == acting_user.id:
        raise RuleError("You cannot deactivate yourself")
    user.is_active = False
    db.commit()
    return user


def change_role(db: Session, user_id: int, data: RoleChange, acting_user: User) -> User:
    """Change a user's role and organisation.

    The organisation is resolved before the user is modified. The lookup
    triggers an autoflush, and a partly updated user (client role without an
    organisation) would violate the CHECK constraint. Admins cannot change
    their own role, which guarantees that at least one admin remains.

    Args:
        db: Database session.
        user_id: Id of the user to change.
        data: New role and organisation.
        acting_user: Admin performing the change.

    Raises:
        NotFoundError: No user has this id.
        RuleError: The organisation does not exist, or the admin targeted their
            own account.
    """
    user = get_user(db, user_id)
    if user.id == acting_user.id:
        raise RuleError("You cannot change your own role")
    organisation_id = find_organisation_id(db, data.organisation)
    user.role = data.role
    user.organisation_id = organisation_id
    db.commit()
    return user
