"""Exceptions raised by the service layer.

Services raise these instead of ``HTTPException``, so they can be used and
tested without HTTP. ``app.main`` maps each one to a status code.
"""


class NotFoundError(Exception):
    """Requested object does not exist or is not visible to the user. Mapped to 404."""


class PermissionDeniedError(Exception):
    """User is not allowed to perform this action on a visible object. Mapped to 403."""


class ConflictError(Exception):
    """Change conflicts with existing data, such as a duplicate email. Mapped to 409."""


class RuleError(Exception):
    """Input is valid but breaks a business rule. Mapped to 400."""
