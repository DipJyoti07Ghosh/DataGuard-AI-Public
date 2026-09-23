"""create dataset_health_results and data_quality_issues tables

Revision ID: 007_create_data_quality_issues
Revises: 006_create_anomaly_results
Create Date: 2026-09-20 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_create_data_quality_issues'
down_revision: Union[str, None] = '006_create_anomaly_results'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create dataset_health_results table
    op.create_table(
        'dataset_health_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('health_score', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('health_grade', sa.String(length=50), nullable=False, server_default='EXCELLENT'),
        sa.Column('quality_health', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('risk_health', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('anomaly_health', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('privacy_health', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('total_issues', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_issues', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('high_issues', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('medium_issues', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_issues', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint('dataset_version_id', name='uq_dataset_health_version_id'),
    )
    op.create_index(op.f('ix_dataset_health_results_id'), 'dataset_health_results', ['id'], unique=False)
    op.create_index(op.f('ix_dataset_health_results_dataset_version_id'), 'dataset_health_results', ['dataset_version_id'], unique=True)

    # 2. Create data_quality_issues table
    op.create_table(
        'data_quality_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_health_result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_health_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=True),
        sa.Column('issue_type', sa.String(length=100), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='LOW'),
        sa.Column('priority_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('affected_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('affected_percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sensitivity_score', sa.Float(), nullable=False, server_default='20.0'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='80.0'),
        sa.Column('evidence_score', sa.Float(), nullable=False, server_default='25.0'),
        sa.Column('risk_context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('recommendation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_data_quality_issues_id'), 'data_quality_issues', ['id'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_dataset_health_result_id'), 'data_quality_issues', ['dataset_health_result_id'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_dataset_version_id'), 'data_quality_issues', ['dataset_version_id'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_column_name'), 'data_quality_issues', ['column_name'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_issue_type'), 'data_quality_issues', ['issue_type'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_source'), 'data_quality_issues', ['source'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_severity'), 'data_quality_issues', ['severity'], unique=False)
    op.create_index(op.f('ix_data_quality_issues_priority_score'), 'data_quality_issues', ['priority_score'], unique=False)
    op.create_index('ix_data_quality_issues_health_priority', 'data_quality_issues', ['dataset_health_result_id', 'priority_score'], unique=False)
    op.create_index('ix_data_quality_issues_version_source', 'data_quality_issues', ['dataset_version_id', 'source'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_data_quality_issues_version_source', table_name='data_quality_issues')
    op.drop_index('ix_data_quality_issues_health_priority', table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_priority_score'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_severity'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_source'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_issue_type'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_column_name'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_dataset_version_id'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_dataset_health_result_id'), table_name='data_quality_issues')
    op.drop_index(op.f('ix_data_quality_issues_id'), table_name='data_quality_issues')
    op.drop_table('data_quality_issues')

    op.drop_index(op.f('ix_dataset_health_results_dataset_version_id'), table_name='dataset_health_results')
    op.drop_index(op.f('ix_dataset_health_results_id'), table_name='dataset_health_results')
    op.drop_table('dataset_health_results')
