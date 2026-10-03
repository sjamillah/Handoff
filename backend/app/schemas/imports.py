"""Episode CSV import report."""

from typing import Literal

from pydantic import BaseModel, Field

ImportOutcome = Literal["duplicate", "conflict", "rejected"]


class ImportRowResult(BaseModel):
    """Outcome of one CSV row that was not imported."""

    line: int = Field(
        description="Line number in the file, counting the header as 1.", examples=[59]
    )
    episode_id: str | None = Field(examples=["EP-00011"])
    outcome: ImportOutcome = Field(examples=["conflict"])
    reason: str = Field(examples=["differs from line 3: quality 'good' vs 'bad'"])


class ImportReport(BaseModel):
    """Result of an episode import: counts per outcome and every row not imported."""

    imported: int = 0
    duplicates: int = 0
    conflicts: int = 0
    rejected: int = 0
    rows: list[ImportRowResult] = Field(default_factory=list)

    def add(self, outcome: ImportOutcome, line: int, episode_id: str | None, reason: str) -> None:
        """Record a row that was not imported and increase the count for its outcome."""
        self.rows.append(
            ImportRowResult(line=line, episode_id=episode_id, outcome=outcome, reason=reason)
        )
        if outcome == "duplicate":
            self.duplicates += 1
        elif outcome == "conflict":
            self.conflicts += 1
        else:
            self.rejected += 1
