"""record role on status history

Revision ID: 663d4eb56688
Revises: 6f66c737bd2f
Create Date: 2026-10-01 16:43:19.124170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '663d4eb56688'
down_revision: Union[str, Sequence[str], None] = '6f66c737bd2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('status_history', sa.Column('changed_by_role', sa.String(length=20), nullable=True))
    op.execute(
        "UPDATE status_history SET changed_by_role = users.role "
        "FROM users WHERE users.id = status_history.changed_by_id"
    )
    op.alter_column('status_history', 'changed_by_role', nullable=False)
    op.create_check_constraint(
        op.f('ck_status_history_changed_by_role_valid'),
        'status_history',
        "changed_by_role IN ('client', 'operator', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_status_history_changed_by_role_valid'), 'status_history', type_='check')
    op.drop_column('status_history', 'changed_by_role')
