"""Add explicit employee document assignments.

Revision ID: 0006_document_assignments
Revises: 0005_embedding_vectors
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_document_assignments"
down_revision = "0005_embedding_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_assignments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_document_assignments_user_id_users"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE", name="fk_document_assignments_document_id_documents"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], name="fk_document_assignments_assigned_by_users"),
        sa.PrimaryKeyConstraint("user_id", "document_id", name="pk_document_assignments"),
    )
    op.create_index("ix_document_assignments_document_id", "document_assignments", ["document_id"])


def downgrade() -> None:
    op.drop_table("document_assignments")
