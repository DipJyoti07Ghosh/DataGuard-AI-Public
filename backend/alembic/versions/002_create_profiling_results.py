"""create profiling_results table

Revision ID: 002_create_profiling
Revises: 001_create_datasets
Create Date: 2026-09-17 19:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_create_profiling'
down_revision: Union[str, None] = '001_create_datasets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'profiling_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('missing_cells', sa.Integer(), nullable=False),
        sa.Column('missing_cells_percentage', sa.Float(), nullable=False),
        sa.Column('duplicate_rows', sa.Integer(), nullable=False),
        sa.Column('duplicate_rows_percentage', sa.Float(), nullable=False),
        sa.Column('memory_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('numeric_columns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('categorical_columns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('datetime_columns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('boolean_columns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('column_profiles', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('correlations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dataset_version_id', name='uq_profiling_result_dataset_version'),
    )
    op.create_index(op.f('ix_profiling_results_id'), 'profiling_results', ['id'], unique=False)
    op.create_index(op.f('ix_profiling_results_dataset_version_id'), 'profiling_results', ['dataset_version_id'], unique=True)


def downgrade() -> None:
    op.drop_table('profiling_results')
