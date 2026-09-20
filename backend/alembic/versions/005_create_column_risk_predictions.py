"""create column_risk_predictions table

Revision ID: 005_create_column_risk
Revises: 004_create_pii_results
Create Date: 2026-09-20 15:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_create_column_risk'
down_revision: Union[str, None] = '004_create_pii_results'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create column_risk_predictions table
    op.create_table(
        'column_risk_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=False),
        sa.Column('predicted_domain', sa.String(length=100), nullable=False),
        sa.Column('model_confidence', sa.Float(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('pii_signal', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('pii_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('pii_detection_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('quality_failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('feature_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('explanation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False, server_default='column-risk-v1'),
        sa.Column('predicted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dataset_version_id', 'column_name', name='uq_version_column_risk'),
    )
    op.create_index(op.f('ix_column_risk_predictions_id'), 'column_risk_predictions', ['id'], unique=False)
    op.create_index(op.f('ix_column_risk_predictions_dataset_version_id'), 'column_risk_predictions', ['dataset_version_id'], unique=False)
    op.create_index(op.f('ix_column_risk_predictions_column_name'), 'column_risk_predictions', ['column_name'], unique=False)
    op.create_index(op.f('ix_column_risk_predictions_predicted_domain'), 'column_risk_predictions', ['predicted_domain'], unique=False)
    op.create_index(op.f('ix_column_risk_predictions_risk_level'), 'column_risk_predictions', ['risk_level'], unique=False)
    op.create_index('ix_column_risk_version_domain', 'column_risk_predictions', ['dataset_version_id', 'predicted_domain'], unique=False)
    op.create_index('ix_column_risk_version_level', 'column_risk_predictions', ['dataset_version_id', 'risk_level'], unique=False)


def downgrade() -> None:
    op.drop_table('column_risk_predictions')
