"""Persist pending document sources across container restarts.

Revision ID: 0010_durable_document_sources
Revises: 0009_ingestion_jobs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_durable_document_sources"
down_revision = "0009_ingestion_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_sources",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"],
            ondelete="CASCADE",
            name="fk_document_sources_document_id_documents",
        ),
        sa.PrimaryKeyConstraint("document_id", name="pk_document_sources"),
    )


def downgrade() -> None:
    op.drop_table("document_sources")
