"""create quality_validation_results and quality_expectation_results tables

Revision ID: 003_create_quality
Revises: 002_create_profiling
Create Date: 2026-09-17 20:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_create_quality'
down_revision: Union[str, None] = '002_create_profiling'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create quality_validation_results table
    op.create_table(
        'quality_validation_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('total_expectations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('passed_expectations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_expectations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint('dataset_version_id', name='uq_quality_validation_dataset_version'),
    )
    op.create_index(op.f('ix_quality_validation_results_id'), 'quality_validation_results', ['id'], unique=False)
    op.create_index(op.f('ix_quality_validation_results_dataset_version_id'), 'quality_validation_results', ['dataset_version_id'], unique=True)

    # 2. Create quality_expectation_results table
    op.create_table(
        'quality_expectation_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('validation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quality_validation_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expectation_type', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('observed_value', sa.String(length=255), nullable=True),
        sa.Column('expected_value', sa.String(length=255), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(op.f('ix_quality_expectation_results_id'), 'quality_expectation_results', ['id'], unique=False)
    op.create_index(op.f('ix_quality_expectation_results_validation_id'), 'quality_expectation_results', ['validation_id'], unique=False)
    op.create_index(op.f('ix_quality_expectation_results_expectation_type'), 'quality_expectation_results', ['expectation_type'], unique=False)
    op.create_index(op.f('ix_quality_expectation_results_category'), 'quality_expectation_results', ['category'], unique=False)
    op.create_index(op.f('ix_quality_expectation_results_column_name'), 'quality_expectation_results', ['column_name'], unique=False)
    op.create_index(op.f('ix_quality_expectation_results_success'), 'quality_expectation_results', ['success'], unique=False)


def downgrade() -> None:
    op.drop_table('quality_expectation_results')
    op.drop_table('quality_validation_results')
