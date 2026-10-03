"""Password hashing.

``DUMMY_HASH`` is verified against when a login email does not exist, so
that the response time matches a wrong password.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()

DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    """Hash a password with argon2id and a random salt.

    Args:
        password: Plain-text password.

    Returns:
        Encoded argon2 hash, including its parameters and salt.
    """
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Check a password against an argon2 hash.

    Args:
        password_hash: Stored argon2 hash.
        password: Plain-text password to check.

    Returns:
        True if the password matches, otherwise False.

    Raises:
        argon2.exceptions.InvalidHashError: The stored hash is malformed.
    """
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
