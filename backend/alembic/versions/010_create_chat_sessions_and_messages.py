"""create chat_sessions and chat_messages tables

Revision ID: 010_create_chat_sessions_and_messages
Revises: 009_create_rag_documents
Create Date: 2026-09-21 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010_create_chat_tables'
down_revision: Union[str, None] = '009_create_rag_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('comparison_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_comparisons.id', ondelete='CASCADE'), nullable=True),
        sa.Column('scope', sa.String(length=32), nullable=False, server_default='VERSION'),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='New Chat'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("scope IN ('VERSION', 'COMPARISON', 'DATASET')", name='chk_chat_session_scope'),
    )
    op.create_index('ix_chat_sessions_id', 'chat_sessions', ['id'])
    op.create_index('ix_chat_sessions_dataset_id', 'chat_sessions', ['dataset_id'])
    op.create_index('ix_chat_sessions_version_id', 'chat_sessions', ['version_id'])
    op.create_index('ix_chat_sessions_comparison_id', 'chat_sessions', ['comparison_id'])
    op.create_index('ix_chat_sessions_dataset_updated', 'chat_sessions', ['dataset_id', 'updated_at'])
    op.create_index('ix_chat_sessions_dataset_created', 'chat_sessions', ['dataset_id', 'created_at'])

    # 2. Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=True),
        sa.Column('model', sa.String(length=128), nullable=True),
        sa.Column('fallback_occurred', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('grounded', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name='chk_chat_message_role'),
    )
    op.create_index('ix_chat_messages_id', 'chat_messages', ['id'])
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('ix_chat_messages_session_created', 'chat_messages', ['session_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
