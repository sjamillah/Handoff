"""Dataset request endpoints.

Clients see only their own requests, and a request belonging to another
client answers 404, the same as one that does not exist. Operators and
admins see every request.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_roles
from app.models import User
from app.schemas import (
    AssignmentIn,
    AssignmentOut,
    ErrorOut,
    RequestCreate,
    RequestDetail,
    RequestOut,
    RequestStatus,
    StatusChangeIn,
)
from app.services import assignments, request_views, requests

router = APIRouter(
    prefix="/requests",
    tags=["requests"],
    responses={401: {"model": ErrorOut}},
)

ClientUser = Annotated[User, Depends(require_roles("client"))]
StaffUser = Annotated[User, Depends(require_roles("operator", "admin"))]


@router.post("", response_model=RequestOut, status_code=201, responses={403: {"model": ErrorOut}})
def create_request(body: RequestCreate, db: DbSession, client: ClientUser) -> RequestOut:
    """Create a request. Clients only. The request starts in ``submitted``."""
    return request_views.request_summary(requests.create_request(db, client, body), client)


@router.get("", response_model=list[RequestOut])
def list_requests(
    db: DbSession, user: CurrentUser, status: RequestStatus | None = None
) -> list[RequestOut]:
    """List requests, newest first. Clients get only their own."""
    visible = requests.list_requests(db, user, status)
    return [request_views.request_summary(request, user) for request in visible]


@router.get("/{request_id}", response_model=RequestDetail, responses={404: {"model": ErrorOut}})
def get_request(request_id: int, db: DbSession, user: CurrentUser) -> RequestDetail:
    """Return one request with its status history.

    Clients see staff changes by role only, without names.
    """
    return request_views.request_detail(requests.get_request(db, user, request_id), user)


@router.post(
    "/{request_id}/transitions",
    response_model=RequestDetail,
    responses={403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def change_status(
    request_id: int, body: StatusChangeIn, db: DbSession, user: CurrentUser
) -> RequestDetail:
    """Move a request to another status.

    Allowed changes: submitted to in_progress, in_progress to delivered and
    rejected to in_progress by operators and admins; delivered to accepted or
    rejected by the client who owns the request. Any other change returns 409.
    """
    request = requests.change_status(db, user, request_id, body.to_status)
    return request_views.request_detail(request, user)


@router.post(
    "/{request_id}/assignments",
    response_model=AssignmentOut,
    status_code=201,
    responses={403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def assign_episodes(
    request_id: int, body: AssignmentIn, db: DbSession, user: StaffUser
) -> AssignmentOut:
    """Assign episodes to an in_progress request. Operators and admins only.

    All or nothing: if any episode is missing, has bad quality or is already
    assigned, nothing is assigned and the error lists every failing episode.
    """
    return assignments.assign_episodes(db, user, request_id, body.episode_ids)


@router.delete(
    "/{request_id}/assignments/{episode_id}",
    status_code=204,
    responses={403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def unassign_episode(request_id: int, episode_id: str, db: DbSession, user: StaffUser) -> None:
    """Remove an episode from an in_progress request. Operators and admins only."""
    assignments.unassign_episode(db, user, request_id, episode_id)
