"""Dataset request endpoints.

Clients see only their own requests, and a request belonging to another
client answers 404, the same as one that does not exist. Operators and
admins see every request.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import CurrentUser, DbSession, require_roles
from app.models import DatasetRequest, User
from app.schemas import (
    ErrorOut,
    RequestCreate,
    RequestDetail,
    RequestOut,
    RequestStatus,
    StatusChangeIn,
)
from app.services import requests

router = APIRouter(
    prefix="/requests",
    tags=["requests"],
    responses={401: {"model": ErrorOut}},
)

ClientUser = Annotated[User, Depends(require_roles("client"))]


@router.post("", response_model=RequestOut, status_code=201, responses={403: {"model": ErrorOut}})
def create_request(body: RequestCreate, db: DbSession, client: ClientUser) -> DatasetRequest:
    """Create a request. Clients only. The request starts in ``submitted``."""
    return requests.create_request(db, client, body)


@router.get("", response_model=list[RequestOut])
def list_requests(
    db: DbSession, user: CurrentUser, status: RequestStatus | None = None
) -> list[DatasetRequest]:
    """List requests, newest first. Clients get only their own."""
    return requests.list_requests(db, user, status)


@router.get("/{request_id}", response_model=RequestDetail, responses={404: {"model": ErrorOut}})
def get_request(request_id: int, db: DbSession, user: CurrentUser) -> DatasetRequest:
    """Return one request with its status history."""
    return requests.get_request(db, user, request_id)


@router.post(
    "/{request_id}/transitions",
    response_model=RequestDetail,
    responses={403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def change_status(
    request_id: int, body: StatusChangeIn, db: DbSession, user: CurrentUser
) -> DatasetRequest:
    """Move a request to another status.

    Allowed changes: submitted to in_progress, in_progress to delivered and
    rejected to in_progress by operators and admins; delivered to accepted or
    rejected by the client who owns the request. Any other change returns 409.
    """
    return requests.change_status(db, user, request_id, body.to_status)
