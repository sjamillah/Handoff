"""Analytics endpoint for operators and admins."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.deps import DbSession, require_roles
from app.schemas import AnalyticsOut, ErrorOut
from app.services.analytics import get_analytics

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_roles("operator", "admin"))],
    responses={401: {"model": ErrorOut}, 403: {"model": ErrorOut}},
)


@router.get("", response_model=AnalyticsOut, responses={400: {"model": ErrorOut}})
def analytics(
    db: DbSession,
    date_from: Annotated[date, Query(alias="from", examples=["2026-08-01"])],
    date_to: Annotated[date, Query(alias="to", examples=["2026-09-30"])],
) -> AnalyticsOut:
    """Episode and request figures for a range of days, both days included.

    Days are calendar days in the business time zone. All figures are computed
    by aggregate queries in the database.
    """
    return get_analytics(db, date_from, date_to)
