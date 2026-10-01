"""initial schema

Revision ID: 97956c0093fd
Revises: 
Create Date: 2026-10-01 11:11:50.889946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '97956c0093fd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('episodes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('episode_id', sa.String(length=100), nullable=False),
    sa.Column('robot_id', sa.String(length=50), nullable=False),
    sa.Column('task_name', sa.String(length=200), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('operator_name', sa.String(length=200), nullable=False),
    sa.Column('quality', sa.String(length=10), nullable=False),
    sa.CheckConstraint("quality IN ('good', 'usable', 'bad')", name=op.f('ck_episodes_quality_valid')),
    sa.CheckConstraint("robot_id IN ('arm-01', 'arm-02', 'arm-03', 'mobile-01', 'humanoid-01')", name=op.f('ck_episodes_robot_known')),
    sa.CheckConstraint('duration_seconds > 0', name=op.f('ck_episodes_duration_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_episodes')),
    sa.UniqueConstraint('episode_id', name=op.f('uq_episodes_episode_id'))
    )
    op.create_index(op.f('ix_episodes_recorded_at'), 'episodes', ['recorded_at'], unique=False)
    op.create_index('ix_episodes_task_name_quality', 'episodes', ['task_name', 'quality'], unique=False)
    op.create_table('organisations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organisations')),
    sa.UniqueConstraint('name', name=op.f('uq_organisations_name'))
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('organisation_id', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(role = 'client') = (organisation_id IS NOT NULL)", name=op.f('ck_users_client_has_organisation')),
    sa.CheckConstraint("role IN ('client', 'operator', 'admin')", name=op.f('ck_users_role_valid')),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'], name=op.f('fk_users_organisation_id_organisations')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('task_name', sa.String(length=200), nullable=False),
    sa.Column('episodes_requested', sa.Integer(), nullable=False),
    sa.Column('deadline', sa.Date(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='submitted', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')", name=op.f('ck_requests_status_valid')),
    sa.CheckConstraint('episodes_requested > 0', name=op.f('ck_requests_episodes_requested_positive')),
    sa.ForeignKeyConstraint(['client_id'], ['users.id'], name=op.f('fk_requests_client_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_requests'))
    )
    op.create_index(op.f('ix_requests_client_id'), 'requests', ['client_id'], unique=False)
    op.create_table('assignments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('episode_id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('assigned_by_id', sa.Integer(), nullable=False),
    sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assigned_by_id'], ['users.id'], name=op.f('fk_assignments_assigned_by_id_users')),
    sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], name=op.f('fk_assignments_episode_id_episodes')),
    sa.ForeignKeyConstraint(['request_id'], ['requests.id'], name=op.f('fk_assignments_request_id_requests')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assignments')),
    sa.UniqueConstraint('episode_id', name=op.f('uq_assignments_episode_id'))
    )
    op.create_index(op.f('ix_assignments_request_id'), 'assignments', ['request_id'], unique=False)
    op.create_table('status_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('from_status', sa.String(length=20), nullable=True),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('changed_by_id', sa.Integer(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("from_status IS NULL OR from_status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')", name=op.f('ck_status_history_from_status_valid')),
    sa.CheckConstraint("to_status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')", name=op.f('ck_status_history_to_status_valid')),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], name=op.f('fk_status_history_changed_by_id_users')),
    sa.ForeignKeyConstraint(['request_id'], ['requests.id'], name=op.f('fk_status_history_request_id_requests')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_status_history'))
    )
    op.create_index(op.f('ix_status_history_request_id'), 'status_history', ['request_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_status_history_request_id'), table_name='status_history')
    op.drop_table('status_history')
    op.drop_index(op.f('ix_assignments_request_id'), table_name='assignments')
    op.drop_table('assignments')
    op.drop_index(op.f('ix_requests_client_id'), table_name='requests')
    op.drop_table('requests')
    op.drop_table('users')
    op.drop_table('organisations')
    op.drop_index('ix_episodes_task_name_quality', table_name='episodes')
    op.drop_index(op.f('ix_episodes_recorded_at'), table_name='episodes')
    op.drop_table('episodes')
