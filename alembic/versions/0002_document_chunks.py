"""Persist extracted document chunks and their embedding status.

Revision ID: 0002_document_chunks
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_document_chunks"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

chunk_status = sa.Enum("PENDING", "EMBEDDED", "FAILED", name="chunk_status")


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(500), nullable=True),
        sa.Column("status", chunk_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_document_chunks_document_id_documents", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_id"),
    )
    op.create_index("ix_document_chunks_department_id", "document_chunks", ["department_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_status", "document_chunks", ["status"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    chunk_status.drop(op.get_bind(), checkfirst=True)
