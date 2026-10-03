"""Import of episodes from the recording system's CSV export.

Rows are normalised, validated and checked for duplicates before insert. Each
row ends in exactly one outcome: imported, duplicate, conflict or rejected.
Existing episodes are never updated, so importing the same file again creates
no rows.

Date assumption: ``dd/mm/yyyy HH:MM`` is read day first, so ``03/08/2026`` is
3 August 2026. Timestamps without a time zone are taken as UTC.
"""

import csv
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import NamedTuple, TextIO

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Episode
from app.models.constants import KNOWN_ROBOTS, QUALITIES
from app.schemas import ImportReport
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
BATCH_SIZE = 1000
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


class ValidRow(NamedTuple):
    """Valid row waiting to be checked against the database."""

    line: int
    values: EpisodeValues


def import_episodes(db: Session, csv_file: TextIO, now: datetime | None = None) -> ImportReport:
    """Import episodes from an open CSV file in a single transaction.

    Args:
        db: Database session. Committed on success, rolled back on failure.
        csv_file: Text file opened with ``newline=""``, as the csv module requires.
        now: Current time, used to reject future timestamps. Defaults to now in UTC.

    Returns:
        Counts per outcome and one entry per row that was not imported.

    Raises:
        RuleError: The file is empty, is not UTF-8, or has the wrong header.
    """
    now = now or datetime.now(UTC)
    report = ImportReport()
    seen: dict[str, ValidRow] = {}
    pending: list[ValidRow] = []
    try:
        for line, fields in read_rows(csv_file):
            values, errors = parse_row(fields, now)
            if errors:
                episode_id = fields.get("episode_id", "").strip().upper() or None
                report.add("rejected", line, episode_id, "; ".join(errors))
                continue
            earlier = seen.get(values.episode_id)
            if earlier:
                record_duplicate(report, line, values, earlier.values, f"line {earlier.line}")
                continue
            seen[values.episode_id] = ValidRow(line, values)
            pending.append(ValidRow(line, values))
            if len(pending) >= BATCH_SIZE:
                insert_batch(db, pending, report)
                pending.clear()
        insert_batch(db, pending, report)
        db.commit()
    except UnicodeDecodeError as exc:
        db.rollback()
        raise RuleError("The file is not valid UTF-8 text") from exc
    except Exception:
        db.rollback()
        raise
    report.rows.sort(key=lambda row: row.line)
    return report


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
                {"episode_id": fields[0].strip().upper(), "_column_count": str(len(fields))},
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
    clean = normalise(fields)
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


def normalise(fields: dict[str, str]) -> dict[str, str]:
    """Strip every field, upper-case episode_id and lower-case robot_id, task_name and quality."""
    clean = {name: value.strip() for name, value in fields.items()}
    clean["episode_id"] = clean["episode_id"].upper()
    for name in ("robot_id", "task_name", "quality"):
        clean[name] = clean[name].lower()
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


def insert_batch(db: Session, batch: list[ValidRow], report: ImportReport) -> None:
    """Compare a batch of new rows with stored episodes and insert the ones that are missing.

    One query loads the stored episodes with the same ids, and one statement
    inserts the rest. ``ON CONFLICT DO NOTHING`` covers an episode inserted by
    another import after the lookup; such a row is counted as a duplicate.
    """
    if not batch:
        return
    ids = [row.values.episode_id for row in batch]
    stored = {
        episode.episode_id: to_values(episode)
        for episode in db.scalars(select(Episode).where(Episode.episode_id.in_(ids)))
    }
    new_rows = []
    for row in batch:
        existing = stored.get(row.values.episode_id)
        if existing:
            record_duplicate(report, row.line, row.values, existing, "the database")
        else:
            new_rows.append(row)
    if not new_rows:
        return
    statement = (
        insert(Episode)
        .values([row.values._asdict() for row in new_rows])
        .on_conflict_do_nothing(index_elements=["episode_id"])
        .returning(Episode.episode_id)
    )
    inserted = set(db.scalars(statement))
    report.imported += len(inserted)
    for row in new_rows:
        if row.values.episode_id not in inserted:
            report.add("duplicate", row.line, row.values.episode_id, "inserted by another import")


def record_duplicate(
    report: ImportReport,
    line: int,
    values: EpisodeValues,
    existing: EpisodeValues,
    source: str,
) -> None:
    """Report a row whose episode_id is already known, as a duplicate or a conflict.

    Args:
        report: Report to add the outcome to.
        line: Line number of the row in the file.
        values: Values of the row.
        existing: Values already known for the same episode_id.
        source: Where the existing values come from, for the message.
    """
    differences = describe_differences(values, existing)
    if differences:
        reason = f"differs from {source}: {differences}"
        report.add("conflict", line, values.episode_id, reason)
    else:
        report.add("duplicate", line, values.episode_id, f"same as {source}")


def describe_differences(values: EpisodeValues, existing: EpisodeValues) -> str:
    """Describe the fields that differ, for example ``quality 'good' vs 'bad'``."""
    return ", ".join(
        f"{name} '{new}' vs '{old}'"
        for name, new, old in zip(EpisodeValues._fields, values, existing, strict=True)
        if new != old
    )


def to_values(episode: Episode) -> EpisodeValues:
    """Return the comparable values of a stored episode."""
    return EpisodeValues(*(getattr(episode, name) for name in EpisodeValues._fields))
