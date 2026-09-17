"""create datasets and dataset_versions tables

Revision ID: 001_create_datasets
Revises: 
Create Date: 2026-09-17 19:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_create_datasets'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create datasets table
    op.create_table(
        'datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_datasets_id'), 'datasets', ['id'], unique=False)
    op.create_index(op.f('ix_datasets_name'), 'datasets', ['name'], unique=True)

    # 2. Create dataset_versions table
    op.create_table(
        'dataset_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=20), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('column_names', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('column_dtypes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('encoding', sa.String(length=50), nullable=True),
        sa.Column('delimiter', sa.String(length=10), nullable=True),
        sa.Column('sheet_name', sa.String(length=100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dataset_id', 'version_number', name='uq_dataset_version_number'),
        sa.CheckConstraint('version_number > 0', name='ck_version_number_positive'),
    )
    op.create_index(op.f('ix_dataset_versions_id'), 'dataset_versions', ['id'], unique=False)
    op.create_index(op.f('ix_dataset_versions_dataset_id'), 'dataset_versions', ['dataset_id'], unique=False)


def downgrade() -> None:
    op.drop_table('dataset_versions')
    op.drop_table('datasets')
