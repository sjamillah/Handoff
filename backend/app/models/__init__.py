"""Database models.

Importing this package registers every table on ``Base.metadata``, which
Alembic autogenerate requires.
"""

from app.models.assignment import Assignment
from app.models.episode import Episode
from app.models.export_job import ExportJob
from app.models.organisation import Organisation
from app.models.request import DatasetRequest
from app.models.status_history import StatusHistory
from app.models.user import User

__all__ = [
    "Assignment",
    "DatasetRequest",
    "Episode",
    "ExportJob",
    "Organisation",
    "StatusHistory",
    "User",
]
