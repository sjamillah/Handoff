"""Normalisation of values that are stored in one place and looked up in another.

Requests are matched to episodes by task name, episodes are found by their CSV
episode_id, and users log in by email. Each value goes through one function
here wherever it is written or searched for, so the two sides always agree.
"""


def normalise_email(email: str) -> str:
    """Return the email trimmed and lower-cased, the form in which emails are stored."""
    return email.strip().lower()


def normalise_task_name(task_name: str) -> str:
    """Return the task name trimmed and lower-cased, so "  Pick Cup " matches "pick cup"."""
    return task_name.strip().lower()


def normalise_episode_id(episode_id: str) -> str:
    """Return the episode id trimmed and upper-cased, so "ep-00003" matches "EP-00003"."""
    return episode_id.strip().upper()
