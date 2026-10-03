"""Import of episodes from the recording system's CSV export.

Rows come validated from ``episode_csv``. This module checks them for
duplicates and stores the new ones. Each row ends in exactly one outcome:
imported, duplicate, conflict or rejected. Existing episodes are never
updated, so importing the same file again creates no rows.
"""

from datetime import UTC, datetime
from typing import NamedTuple, TextIO

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Episode
from app.normalise import normalise_episode_id
from app.schemas import ImportReport
from app.services.episode_csv import EpisodeValues, parse_row, read_rows
from app.services.errors import RuleError

BATCH_SIZE = 1000


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
                episode_id = normalise_episode_id(fields.get("episode_id", "")) or None
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
