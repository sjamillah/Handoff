from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

hasher = PasswordHasher()

DUMMY_HASH = hasher.hash("not-a-real-password")


def hash_password(password):
    return hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def normalise_email(email):
    return email.strip().lower()
