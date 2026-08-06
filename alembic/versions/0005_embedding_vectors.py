"""Persist Qdrant vector identifiers and embedding lineage.

Revision ID: 0005_embedding_vectors
Revises: 0004_slack_metadata
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_embedding_vectors"
down_revision = "0004_slack_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("vector_id", sa.String(64), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(100), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_checksum", sa.String(64), nullable=True))
    op.add_column("document_chunks", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_document_chunks_vector_id", "document_chunks", ["vector_id"], unique=True)
    op.create_index("ix_document_chunks_embedding_checksum", "document_chunks", ["embedding_checksum"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_checksum", table_name="document_chunks")
    op.drop_index("ix_document_chunks_vector_id", table_name="document_chunks")
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_checksum")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "vector_id")
