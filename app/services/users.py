from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Organisation, User
from app.security import DUMMY_HASH, hash_password, normalise_email, verify_password
from app.services.errors import ConflictError, NotFoundError, RuleError


def authenticate(db, email, password):
    """Returns the user, or None if the login fails for any reason.

    If the email doesn't exist we still check the password against a dummy hash,
    so it takes about as long and doesn't give away which emails are real.
    """
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    password_ok = verify_password(user.password_hash if user else DUMMY_HASH, password)
    if user and user.is_active and password_ok:
        return user
    return None


def find_organisation_id(db, name):
    if name is None:
        return None
    organisation_id = db.scalar(select(Organisation.id).where(Organisation.name == name))
    if organisation_id is None:
        raise RuleError(f"Unknown organisation: {name}")
    return organisation_id


def get_user(db, user_id):
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def create_user(db, data):
    """Duplicate emails are caught by the UNIQUE constraint, not by checking first,
    so two requests at the same time can't both get through.
    """
    user = User(
        email=normalise_email(data.email),
        password_hash=hash_password(data.password),
        role=data.role,
        organisation_id=find_organisation_id(db, data.organisation),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A user with this email already exists")
    db.refresh(user)
    return user


def deactivate_user(db, user_id, acting_user):
    user = get_user(db, user_id)
    if user.id == acting_user.id:
        raise RuleError("You cannot deactivate yourself")
    user.is_active = False
    db.commit()
    return user


def change_role(db, user_id, data, acting_user):
    """Looks up the organisation before touching the user.

    The query autoflushes, and a user caught half way to becoming a client
    (role set, no organisation yet) breaks the CHECK constraint.
    """
    user = get_user(db, user_id)
    if user.id == acting_user.id:
        raise RuleError("You cannot change your own role")
    organisation_id = find_organisation_id(db, data.organisation)
    user.role = data.role
    user.organisation_id = organisation_id
    db.commit()
    return user
