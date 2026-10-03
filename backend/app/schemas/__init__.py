"""Pydantic request and response models, grouped by topic.

Every model is re-exported here, so callers import from ``app.schemas``.
"""

from app.schemas.analytics import AnalyticsOut, DailyRobotCount, StatusCount, TaskCount
from app.schemas.common import ErrorOut, Quality, RequestStatus, Role
from app.schemas.episodes import AssignmentIn, AssignmentOut, EpisodeOut, EpisodePage
from app.schemas.imports import ImportOutcome, ImportReport, ImportRowResult
from app.schemas.requests import (
    RequestCreate,
    RequestDetail,
    RequestOut,
    StatusChangeIn,
    StatusChangeOut,
)
from app.schemas.users import LoginIn, RoleChange, RoleWithOrganisation, UserCreate, UserOut

__all__ = [
    "AnalyticsOut",
    "AssignmentIn",
    "AssignmentOut",
    "DailyRobotCount",
    "EpisodeOut",
    "EpisodePage",
    "ErrorOut",
    "ImportOutcome",
    "ImportReport",
    "ImportRowResult",
    "LoginIn",
    "Quality",
    "RequestCreate",
    "RequestDetail",
    "RequestOut",
    "RequestStatus",
    "Role",
    "RoleChange",
    "RoleWithOrganisation",
    "StatusChangeIn",
    "StatusChangeOut",
    "StatusCount",
    "TaskCount",
    "UserCreate",
    "UserOut",
]
