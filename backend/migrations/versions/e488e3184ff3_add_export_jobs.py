"""add export jobs

Revision ID: e488e3184ff3
Revises: 7f91887cbee1
Create Date: 2026-10-03 16:08:25.981282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e488e3184ff3'
down_revision: Union[str, Sequence[str], None] = '7f91887cbee1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('export_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('assignment_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('next_run_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(status = 'running') = (locked_until IS NOT NULL)", name=op.f('ck_export_jobs_lease_only_while_running')),
    sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name=op.f('ck_export_jobs_status_valid')),
    sa.CheckConstraint('attempts BETWEEN 0 AND max_attempts', name=op.f('ck_export_jobs_attempts_in_range')),
    sa.CheckConstraint('max_attempts > 0', name=op.f('ck_export_jobs_max_attempts_positive')),
    sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], name=op.f('fk_export_jobs_assignment_id_assignments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_export_jobs')),
    sa.UniqueConstraint('assignment_id', name=op.f('uq_export_jobs_assignment_id'))
    )
    op.create_index('ix_export_jobs_due', 'export_jobs', ['next_run_at'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index('ix_export_jobs_lease', 'export_jobs', ['locked_until'], unique=False, postgresql_where=sa.text("status = 'running'"))
    op.execute("INSERT INTO export_jobs (assignment_id, max_attempts) SELECT id, 5 FROM assignments")


def downgrade() -> None:
    op.drop_index('ix_export_jobs_lease', table_name='export_jobs', postgresql_where=sa.text("status = 'running'"))
    op.drop_index('ix_export_jobs_due', table_name='export_jobs', postgresql_where=sa.text("status = 'pending'"))
    op.drop_table('export_jobs')
