"""Service errors. main.py turns them into 404, 409 and 400 responses."""


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class RuleError(Exception):
    """Valid input that breaks a business rule, like an admin deactivating themselves."""
