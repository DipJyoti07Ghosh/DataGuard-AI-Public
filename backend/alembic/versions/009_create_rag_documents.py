"""create rag_documents table with native pgvector support

Revision ID: 009_create_rag_documents
Revises: 008_create_dataset_comparisons
Create Date: 2026-09-21 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '009_create_rag_documents'
down_revision: Union[str, None] = '008_create_dataset_comparisons'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure pgvector extension is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create rag_documents table
    op.create_table(
        'rag_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_versions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('comparison_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dataset_comparisons.id', ondelete='CASCADE'), nullable=True),
        sa.Column('source_result_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_result_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_phase', sa.String(length=50), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('logical_document_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('doc_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('embedding_provider', sa.String(length=50), nullable=False, server_default='fastembed'),
        sa.Column('embedding_model', sa.String(length=100), nullable=False, server_default='BAAI/bge-small-en-v1.5'),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False, server_default='384'),
        sa.Column('embedding_model_version', sa.String(length=50), nullable=False, server_default='1.5'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. Create standard B-tree indexes
    op.create_index(op.f('ix_rag_documents_id'), 'rag_documents', ['id'], unique=False)
    op.create_index(op.f('ix_rag_documents_dataset_id'), 'rag_documents', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_rag_documents_version_id'), 'rag_documents', ['version_id'], unique=False)
    op.create_index(op.f('ix_rag_documents_comparison_id'), 'rag_documents', ['comparison_id'], unique=False)
    op.create_index('ix_rag_documents_dataset_version', 'rag_documents', ['dataset_id', 'version_id'], unique=False)
    op.create_index(op.f('ix_rag_documents_logical_document_id'), 'rag_documents', ['logical_document_id'], unique=False)
    op.create_index(op.f('ix_rag_documents_content_hash'), 'rag_documents', ['content_hash'], unique=False)

    # 4. Create GIN index on doc_metadata JSONB
    op.execute("CREATE INDEX ix_rag_documents_metadata_gin ON rag_documents USING gin (doc_metadata);")

    # 5. Create HNSW index on embedding for fast cosine similarity search
    op.execute("CREATE INDEX ix_rag_documents_embedding_hnsw ON rag_documents USING hnsw (embedding vector_cosine_ops);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_documents_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_rag_documents_metadata_gin;")
    op.drop_index(op.f('ix_rag_documents_content_hash'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_logical_document_id'), table_name='rag_documents')
    op.drop_index('ix_rag_documents_dataset_version', table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_comparison_id'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_version_id'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_dataset_id'), table_name='rag_documents')
    op.drop_index(op.f('ix_rag_documents_id'), table_name='rag_documents')
    op.drop_table('rag_documents')
