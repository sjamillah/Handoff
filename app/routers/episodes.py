"""Episode endpoints for operators and admins."""

import io

from fastapi import APIRouter, Depends, UploadFile

from app.deps import DbSession, require_roles
from app.schemas import ErrorOut, ImportReport
from app.services.episode_import import import_episodes

router = APIRouter(
    prefix="/episodes",
    tags=["episodes"],
    dependencies=[Depends(require_roles("operator", "admin"))],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}},
)


@router.post("/import", response_model=ImportReport, responses={400: {"model": ErrorOut}})
def import_csv(file: UploadFile, db: DbSession) -> ImportReport:
    """Import episodes from a CSV export of the recording system.

    Safe to repeat: episodes that already exist are never changed, so a second
    upload of the same file imports nothing. Dates in ``dd/mm/yyyy HH:MM`` form
    are read day first, and timestamps without a time zone are taken as UTC.
    The report lists every row that was not imported, with the reason.
    """
    text = io.TextIOWrapper(file.file, encoding="utf-8-sig", newline="")
    return import_episodes(db, text)
