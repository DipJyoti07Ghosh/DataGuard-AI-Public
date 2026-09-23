"""add user_id to datasets and chat_sessions

Revision ID: 011_add_auth_and_user_id
Revises: 010_create_chat_tables
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '011_add_auth_and_user_id'
down_revision: Union[str, None] = '010_create_chat_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'datasets',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_datasets_user_id_auth_users',
        'datasets', 'users',
        ['user_id'], ['id'],
        referent_schema='auth',
        ondelete='SET NULL',
    )
    op.create_index('ix_datasets_user_id', 'datasets', ['user_id'])

    op.add_column(
        'chat_sessions',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_chat_sessions_user_id_auth_users',
        'chat_sessions', 'users',
        ['user_id'], ['id'],
        referent_schema='auth',
        ondelete='CASCADE',
    )
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_user_id', table_name='chat_sessions')
    op.drop_constraint('fk_chat_sessions_user_id_auth_users', 'chat_sessions', type_='foreignkey')
    op.drop_column('chat_sessions', 'user_id')

    op.drop_index('ix_datasets_user_id', table_name='datasets')
    op.drop_constraint('fk_datasets_user_id_auth_users', 'datasets', type_='foreignkey')
    op.drop_column('datasets', 'user_id')