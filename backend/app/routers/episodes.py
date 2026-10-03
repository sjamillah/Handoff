"""Episode endpoints for operators and admins."""

import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query, UploadFile

from app.deps import DbSession, require_roles
from app.schemas import EpisodePage, ErrorOut, ImportReport, Quality
from app.services import episodes
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


@router.get("", response_model=EpisodePage)
def list_episodes(
    db: DbSession,
    task_name: str | None = None,
    quality: Quality | None = None,
    request_id: int | None = None,
    assignable: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EpisodePage:
    """List episodes, newest recording first, with filters and pagination.

    ``task_name`` matches exactly, ignoring case and surrounding spaces.
    ``assignable=true`` keeps only good or usable episodes that are not assigned.
    ``request_id`` keeps only the episodes assigned to that request.
    """
    return episodes.list_episodes(
        db,
        task_name=task_name,
        quality=quality,
        request_id=request_id,
        assignable=assignable,
        limit=limit,
        offset=offset,
    )
