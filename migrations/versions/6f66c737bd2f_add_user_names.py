"""add user names

Revision ID: 6f66c737bd2f
Revises: 97956c0093fd
Create Date: 2026-10-01 12:30:56.573926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6f66c737bd2f'
down_revision: Union[str, Sequence[str], None] = '97956c0093fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('name', sa.String(length=200), nullable=True))
    op.execute("UPDATE users SET name = email WHERE name IS NULL")
    op.alter_column('users', 'name', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'name')
