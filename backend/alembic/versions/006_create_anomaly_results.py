"""create anomaly_detection_results and anomaly_findings tables

Revision ID: 006_create_anomaly_results
Revises: 005_create_column_risk
Create Date: 2026-09-20 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_create_anomaly_results'
down_revision: Union[str, None] = '005_create_column_risk'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create anomaly_detection_results table
    op.create_table(
        'anomaly_detection_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('total_columns_analyzed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('columns_with_anomalies', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_anomalies', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('high_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('medium_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dataset_anomaly_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint('dataset_version_id', name='uq_anomaly_results_version_id'),
    )
    op.create_index(op.f('ix_anomaly_detection_results_id'), 'anomaly_detection_results', ['id'], unique=False)
    op.create_index(op.f('ix_anomaly_detection_results_dataset_version_id'), 'anomaly_detection_results', ['dataset_version_id'], unique=True)

    # 2. Create anomaly_findings table
    op.create_table(
        'anomaly_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('detection_result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('anomaly_detection_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=False),
        sa.Column('detection_method', sa.String(length=100), nullable=False),
        sa.Column('anomaly_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('anomaly_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='LOW'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('statistical_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('explanation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index(op.f('ix_anomaly_findings_id'), 'anomaly_findings', ['id'], unique=False)
    op.create_index(op.f('ix_anomaly_findings_detection_result_id'), 'anomaly_findings', ['detection_result_id'], unique=False)
    op.create_index(op.f('ix_anomaly_findings_column_name'), 'anomaly_findings', ['column_name'], unique=False)
    op.create_index('ix_anomaly_findings_result_severity', 'anomaly_findings', ['detection_result_id', 'severity'], unique=False)
    op.create_index('ix_anomaly_findings_result_score', 'anomaly_findings', ['detection_result_id', 'score'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_anomaly_findings_result_score', table_name='anomaly_findings')
    op.drop_index('ix_anomaly_findings_result_severity', table_name='anomaly_findings')
    op.drop_index(op.f('ix_anomaly_findings_column_name'), table_name='anomaly_findings')
    op.drop_index(op.f('ix_anomaly_findings_detection_result_id'), table_name='anomaly_findings')
    op.drop_index(op.f('ix_anomaly_findings_id'), table_name='anomaly_findings')
    op.drop_table('anomaly_findings')

    op.drop_index(op.f('ix_anomaly_detection_results_dataset_version_id'), table_name='anomaly_detection_results')
    op.drop_index(op.f('ix_anomaly_detection_results_id'), table_name='anomaly_detection_results')
    op.drop_table('anomaly_detection_results')
