"""Command line import of an episodes CSV file.

Usage: ``python -m app.import_episodes seed/episodes.csv``. Runs the same
service as ``POST /episodes/import``, prints the report and exits with status 1
if the file cannot be imported at all.
"""

import argparse
import sys

from app.db import SessionLocal
from app.schemas import ImportReport
from app.services.episode_import import import_episodes
from app.services.errors import RuleError


def print_report(report: ImportReport) -> None:
    """Print the counts, then one line per row that was not imported."""
    print(
        f"imported: {report.imported}, duplicates: {report.duplicates}, "
        f"conflicts: {report.conflicts}, rejected: {report.rejected}"
    )
    for row in report.rows:
        print(f"line {row.line:>5}  {row.outcome:<9}  {row.episode_id or '-':<10}  {row.reason}")


def main() -> int:
    """Parse the arguments, run the import and return the exit status."""
    parser = argparse.ArgumentParser(description="Import episodes from a CSV file.")
    parser.add_argument("path", help="path to the CSV file")
    args = parser.parse_args()
    try:
        with open(args.path, encoding="utf-8-sig", newline="") as csv_file, SessionLocal() as db:
            report = import_episodes(db, csv_file)
    except (OSError, RuleError) as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 1
    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
