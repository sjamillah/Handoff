"""Reading and validating rows of the recording system's episode CSV export.

This module only turns text into validated values or a list of problems. It
does not touch the database; ``episode_import`` decides what to store.

Date assumption: ``dd/mm/yyyy HH:MM`` is read day first, so ``03/08/2026`` is
3 August 2026. Timestamps without a time zone are taken as UTC.
"""

import csv
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import NamedTuple, TextIO

from app.models.constants import KNOWN_ROBOTS, QUALITIES
from app.normalise import normalise_episode_id, normalise_task_name
from app.services.errors import RuleError

COLUMNS = (
    "episode_id",
    "robot_id",
    "task_name",
    "recorded_at",
    "duration_seconds",
    "operator_name",
    "quality",
)
MAX_DURATION_SECONDS = 3600
MAX_LENGTHS = {"episode_id": 100, "task_name": 200, "operator_name": 200}
DAY_FIRST_FORMAT = "%d/%m/%Y %H:%M"
INTEGER = re.compile(r"-?\d+")


class EpisodeValues(NamedTuple):
    """Normalised, validated values of one episode, in the order used for comparison."""

    episode_id: str
    robot_id: str
    task_name: str
    recorded_at: datetime
    duration_seconds: int
    operator_name: str
    quality: str


def read_rows(csv_file: TextIO) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield each data row with its line number, keyed by column name.

    Blank and whitespace-only lines are skipped. A row with the wrong number of
    fields is yielded with a ``_column_count`` entry so that it is rejected.

    Raises:
        RuleError: The file is empty or the header does not match ``COLUMNS``.
    """
    reader = csv.reader(csv_file)
    header = next(reader, None)
    if header is None:
        raise RuleError("The file is empty")
    columns = [name.strip().lower() for name in header]
    if sorted(columns) != sorted(COLUMNS):
        raise RuleError(f"Expected the columns {', '.join(COLUMNS)}, got {', '.join(columns)}")
    for fields in reader:
        if not any(field.strip() for field in fields):
            continue
        if len(fields) != len(columns):
            yield (
                reader.line_num,
                {"episode_id": fields[0], "_column_count": str(len(fields))},
            )
            continue
        yield reader.line_num, dict(zip(columns, fields, strict=True))


def parse_row(fields: dict[str, str], now: datetime) -> tuple[EpisodeValues | None, list[str]]:
    """Normalise and validate one row.

    Returns:
        The episode values and an empty list, or None and every problem found.
    """
    if "_column_count" in fields:
        return None, [f"expected {len(COLUMNS)} columns, got {fields['_column_count']}"]
    clean = normalise_fields(fields)
    errors = []
    for name in ("episode_id", "task_name", "operator_name"):
        if not clean[name]:
            errors.append(f"{name} is blank")
        elif len(clean[name]) > MAX_LENGTHS[name]:
            errors.append(f"{name} is longer than {MAX_LENGTHS[name]} characters")
    if not clean["robot_id"]:
        errors.append("robot_id is blank")
    elif clean["robot_id"] not in KNOWN_ROBOTS:
        errors.append(f"unknown robot_id '{clean['robot_id']}'")
    if not clean["quality"]:
        errors.append("quality is blank")
    elif clean["quality"] not in QUALITIES:
        errors.append(f"invalid quality '{clean['quality']}'")
    recorded_at = parse_recorded_at(clean["recorded_at"], now, errors)
    duration = parse_duration(clean["duration_seconds"], errors)
    if errors:
        return None, errors
    values = EpisodeValues(
        episode_id=clean["episode_id"],
        robot_id=clean["robot_id"],
        task_name=clean["task_name"],
        recorded_at=recorded_at,
        duration_seconds=duration,
        operator_name=clean["operator_name"],
        quality=clean["quality"],
    )
    return values, []


def normalise_fields(fields: dict[str, str]) -> dict[str, str]:
    """Strip every field, and normalise the ones that are matched against other data."""
    clean = {name: value.strip() for name, value in fields.items()}
    clean["episode_id"] = normalise_episode_id(clean["episode_id"])
    clean["task_name"] = normalise_task_name(clean["task_name"])
    clean["robot_id"] = clean["robot_id"].lower()
    clean["quality"] = clean["quality"].lower()
    return clean


def parse_recorded_at(value: str, now: datetime, errors: list[str]) -> datetime | None:
    """Parse a timestamp in ISO 8601 or ``dd/mm/yyyy HH:MM`` form and return it in UTC.

    ISO 8601 covers ``2026-08-16T23:28:00``, ``2026-08-16 23:28:00`` and
    ``2026-08-16T23:28:00Z``. Values without a time zone are taken as UTC.
    Appends a message to ``errors`` and returns None when the value is blank,
    cannot be parsed, or lies in the future.
    """
    if not value:
        errors.append("recorded_at is blank")
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value, DAY_FIRST_FORMAT)
        except ValueError:
            errors.append(f"recorded_at '{value}' is not a recognised date")
            return None
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    if parsed > now:
        errors.append(f"recorded_at '{value}' is in the future")
        return None
    return parsed


def parse_duration(value: str, errors: list[str]) -> int | None:
    """Parse duration_seconds as a whole number between 1 and ``MAX_DURATION_SECONDS``.

    Appends a message to ``errors`` and returns None for any other value.
    """
    if not value:
        errors.append("duration_seconds is blank")
        return None
    if not INTEGER.fullmatch(value):
        errors.append(f"duration_seconds '{value}' is not a whole number")
        return None
    duration = int(value)
    if duration <= 0:
        errors.append(f"duration_seconds {duration} is not positive")
        return None
    if duration > MAX_DURATION_SECONDS:
        errors.append(f"duration_seconds {duration} is over the {MAX_DURATION_SECONDS} limit")
        return None
    return duration
