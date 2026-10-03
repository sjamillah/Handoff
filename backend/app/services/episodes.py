"""Listing episodes for operators."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Assignment, Episode
from app.normalise import normalise_task_name
from app.schemas import EpisodeOut, EpisodePage

ASSIGNABLE_QUALITIES = ("good", "usable")


def list_episodes(
    db: Session,
    *,
    task_name: str | None = None,
    quality: str | None = None,
    request_id: int | None = None,
    assignable: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> EpisodePage:
    """Return one page of episodes, newest recording first, and the total that match.

    Args:
        db: Database session.
        task_name: Exact task name. Trimmed and lower-cased like imported episodes.
        quality: Only episodes of this quality.
        request_id: Only episodes assigned to this request.
        assignable: Only episodes that could be assigned now: good or usable and
            not assigned to any request.
        limit: Page size.
        offset: Number of matching episodes to skip.
    """
    query = select(Episode, Assignment.request_id).outerjoin(
        Assignment, Assignment.episode_id == Episode.id
    )
    if task_name:
        query = query.where(Episode.task_name == normalise_task_name(task_name))
    if quality:
        query = query.where(Episode.quality == quality)
    if request_id is not None:
        query = query.where(Assignment.request_id == request_id)
    if assignable:
        query = query.where(
            Episode.quality.in_(ASSIGNABLE_QUALITIES), Assignment.request_id.is_(None)
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Episode.recorded_at.desc(), Episode.id.desc()).limit(limit).offset(offset)
    )
    items = [
        EpisodeOut(
            episode_id=episode.episode_id,
            robot_id=episode.robot_id,
            task_name=episode.task_name,
            recorded_at=episode.recorded_at,
            duration_seconds=episode.duration_seconds,
            operator_name=episode.operator_name,
            quality=episode.quality,
            assigned_request_id=assigned_to,
        )
        for episode, assigned_to in rows
    ]
    return EpisodePage(items=items, total=total or 0, limit=limit, offset=offset)
