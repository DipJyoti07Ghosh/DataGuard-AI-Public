"""create dataset_comparisons and column_drift_results tables

Revision ID: 008_create_dataset_comparisons
Revises: 007_create_data_quality_issues
Create Date: 2026-09-21 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008_create_dataset_comparisons'
down_revision: Union[str, None] = '007_create_data_quality_issues'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create dataset_comparisons table
    op.create_table(
        'dataset_comparisons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('baseline_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='COMPLETED'),
        sa.Column('overall_drift_status', sa.String(length=50), nullable=False, server_default='NO_DRIFT'),
        sa.Column('schema_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('numerical_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('categorical_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('missingness_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('uniqueness_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('quality_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('risk_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('anomaly_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('privacy_drift_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('drift_drivers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('compared_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dataset_id', 'baseline_version_id', 'current_version_id', name='uq_dataset_version_comparison'),
    )
    op.create_index(op.f('ix_dataset_comparisons_id'), 'dataset_comparisons', ['id'], unique=False)
    op.create_index(op.f('ix_dataset_comparisons_dataset_id'), 'dataset_comparisons', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_dataset_comparisons_baseline_version_id'), 'dataset_comparisons', ['baseline_version_id'], unique=False)
    op.create_index(op.f('ix_dataset_comparisons_current_version_id'), 'dataset_comparisons', ['current_version_id'], unique=False)

    # 2. Create column_drift_results table
    op.create_table(
        'column_drift_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('comparison_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_comparisons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=False),
        sa.Column('schema_status', sa.String(length=50), nullable=False, server_default='UNCHANGED'),
        sa.Column('baseline_type', sa.String(length=100), nullable=True),
        sa.Column('current_type', sa.String(length=100), nullable=True),
        sa.Column('type_category', sa.String(length=50), nullable=True),
        sa.Column('drift_status', sa.String(length=50), nullable=False, server_default='NO_DRIFT'),
        sa.Column('missingness_comparison', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('uniqueness_comparison', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('statistical_comparison', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('quality_impact', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('risk_impact', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('anomaly_impact', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('privacy_impact', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('drift_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index(op.f('ix_column_drift_results_id'), 'column_drift_results', ['id'], unique=False)
    op.create_index(op.f('ix_column_drift_results_comparison_id'), 'column_drift_results', ['comparison_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_column_drift_results_comparison_id'), table_name='column_drift_results')
    op.drop_index(op.f('ix_column_drift_results_id'), table_name='column_drift_results')
    op.drop_table('column_drift_results')

    op.drop_index(op.f('ix_dataset_comparisons_current_version_id'), table_name='dataset_comparisons')
    op.drop_index(op.f('ix_dataset_comparisons_baseline_version_id'), table_name='dataset_comparisons')
    op.drop_index(op.f('ix_dataset_comparisons_dataset_id'), table_name='dataset_comparisons')
    op.drop_index(op.f('ix_dataset_comparisons_id'), table_name='dataset_comparisons')
    op.drop_table('dataset_comparisons')
