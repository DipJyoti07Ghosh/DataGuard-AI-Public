"""create pii_scan_results and pii_findings tables

Revision ID: 004_create_pii_results
Revises: 003_create_quality
Create Date: 2026-09-17 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_create_pii_results'
down_revision: Union[str, None] = '003_create_quality'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create pii_scan_results table
    op.create_table(
        'pii_scan_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scanned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('total_columns_scanned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pii_columns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_findings', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint('dataset_version_id', name='uq_pii_scan_dataset_version'),
    )
    op.create_index(op.f('ix_pii_scan_results_id'), 'pii_scan_results', ['id'], unique=False)
    op.create_index(op.f('ix_pii_scan_results_dataset_version_id'), 'pii_scan_results', ['dataset_version_id'], unique=True)

    # 2. Create pii_findings table
    op.create_table(
        'pii_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pii_scan_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('detection_source', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('sampled_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('detected_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('detection_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('masked_preview', sa.String(length=255), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index(op.f('ix_pii_findings_id'), 'pii_findings', ['id'], unique=False)
    op.create_index(op.f('ix_pii_findings_scan_id'), 'pii_findings', ['scan_id'], unique=False)
    op.create_index(op.f('ix_pii_findings_column_name'), 'pii_findings', ['column_name'], unique=False)
    op.create_index(op.f('ix_pii_findings_entity_type'), 'pii_findings', ['entity_type'], unique=False)
    op.create_index(op.f('ix_pii_findings_risk_level'), 'pii_findings', ['risk_level'], unique=False)
    op.create_index('ix_pii_findings_scan_entity', 'pii_findings', ['scan_id', 'entity_type'], unique=False)
    op.create_index('ix_pii_findings_scan_risk', 'pii_findings', ['scan_id', 'risk_level'], unique=False)


def downgrade() -> None:
    op.drop_table('pii_findings')
    op.drop_table('pii_scan_results')
