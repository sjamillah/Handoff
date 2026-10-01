ROLES = ("client", "operator", "admin")
QUALITIES = ("good", "usable", "bad")
REQUEST_STATUSES = ("submitted", "in_progress", "delivered", "accepted", "rejected")
KNOWN_ROBOTS = ("arm-01", "arm-02", "arm-03", "mobile-01", "humanoid-01")


def sql_in(column, values):
    """Turns ("good", "bad") into "quality IN ('good', 'bad')" for a CHECK constraint."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
