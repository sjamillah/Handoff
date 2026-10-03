"""index episodes for analytics

Revision ID: 7f91887cbee1
Revises: 663d4eb56688
Create Date: 2026-10-03 11:57:13.678467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f91887cbee1'
down_revision: Union[str, Sequence[str], None] = '663d4eb56688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_episodes_recorded_at_robot_id', 'episodes', ['recorded_at', 'robot_id'], unique=False)
    op.create_index('ix_episodes_good_recorded_at_task_name', 'episodes', ['recorded_at', 'task_name'], unique=False, postgresql_where=sa.text("quality = 'good'"))
    op.drop_index(op.f('ix_episodes_recorded_at'), table_name='episodes')


def downgrade() -> None:
    op.create_index(op.f('ix_episodes_recorded_at'), 'episodes', ['recorded_at'], unique=False)
    op.drop_index('ix_episodes_good_recorded_at_task_name', table_name='episodes', postgresql_where=sa.text("quality = 'good'"))
    op.drop_index('ix_episodes_recorded_at_robot_id', table_name='episodes')
