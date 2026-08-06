"""Add durable RAG audit events.

Revision ID: 0007_audit_events
Revises: 0006_document_assignments
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_audit_events"
down_revision = "0006_document_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        sa.Column("document_ids", postgresql.JSONB(), nullable=False),
        sa.Column("chunk_ids", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_events_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    for column in ("action", "outcome", "question_hash", "user_id"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])


def downgrade() -> None:
    op.drop_table("audit_events")
