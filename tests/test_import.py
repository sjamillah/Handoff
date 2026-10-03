"""Episode CSV import: idempotency and the per-row report."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, update

from app.models import Episode
from app.services.episode_import import import_episodes

FIXTURE = Path(__file__).parent / "data" / "episodes_small.csv"
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def run_import(db):
    with FIXTURE.open(encoding="utf-8", newline="") as csv_file:
        return import_episodes(db, csv_file, now=NOW)


def episode_count(db):
    return db.scalar(select(func.count(Episode.id)))


def test_importing_the_same_file_twice_creates_no_new_rows(db):
    first = run_import(db)
    count_after_first = episode_count(db)
    second = run_import(db)
    assert first.imported == 2
    assert second.imported == 0
    assert episode_count(db) == count_after_first == 2


def test_report_lists_duplicates_conflicts_and_rejections_by_line(db):
    report = run_import(db)
    assert (report.imported, report.duplicates, report.conflicts, report.rejected) == (2, 1, 1, 8)
    outcomes = {row.line: (row.outcome, row.reason) for row in report.rows}
    assert outcomes[4] == ("duplicate", "same as line 2")
    assert outcomes[5] == ("conflict", "differs from line 3: quality 'bad' vs 'usable'")
    expected_rejections = {
        6: "episode_id is blank",
        7: "unknown robot_id 'arm-99'",
        8: "invalid quality 'excellent'",
        9: "duration_seconds '4.5' is not a whole number",
        10: "recorded_at 'not a date' is not a recognised date",
        11: "recorded_at '2099-01-01T00:00:00' is in the future",
        12: "expected 7 columns, got 5",
        13: "operator_name is blank",
    }
    for line, reason in expected_rejections.items():
        assert outcomes[line] == ("rejected", reason)


def test_second_import_reports_stored_rows_as_duplicates(db):
    run_import(db)
    report = run_import(db)
    assert (report.imported, report.duplicates, report.conflicts, report.rejected) == (0, 3, 1, 8)


def test_row_that_differs_from_the_database_is_a_conflict_and_not_overwritten(db):
    run_import(db)
    db.execute(update(Episode).where(Episode.episode_id == "EP-T001").values(quality="bad"))
    db.commit()
    report = run_import(db)
    outcomes = {row.line: (row.outcome, row.reason) for row in report.rows}
    assert outcomes[2] == ("conflict", "differs from the database: quality 'good' vs 'bad'")
    db.expire_all()
    stored = db.scalar(select(Episode.quality).where(Episode.episode_id == "EP-T001"))
    assert stored == "bad"
