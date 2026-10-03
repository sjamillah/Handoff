"""Allowed values for roles, episode quality, request status and robots.

``ASSIGNABLE_REQUEST_STATUSES`` lists the statuses in which episodes can be
assigned to or removed from a request.
"""

from collections.abc import Iterable

ROLES = ("client", "operator", "admin")
QUALITIES = ("good", "usable", "bad")
REQUEST_STATUSES = ("submitted", "in_progress", "delivered", "accepted", "rejected")
KNOWN_ROBOTS = ("arm-01", "arm-02", "arm-03", "mobile-01", "humanoid-01")
ASSIGNABLE_REQUEST_STATUSES = ("in_progress",)
EXPORT_STATUSES = ("pending", "running", "succeeded", "failed")


def sql_in(column: str, values: Iterable[str]) -> str:
    """Build a SQL ``IN`` expression for a CHECK constraint.

    Args:
        column: Column name.
        values: Allowed values. Must be trusted constants, never user input.

    Returns:
        An expression such as ``quality IN ('good', 'bad')``.
    """
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
