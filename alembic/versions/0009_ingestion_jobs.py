"""Add durable Celery ingestion job progress.

Revision ID: 0009_ingestion_jobs
Revises: 0008_chat_sessions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_ingestion_jobs"
down_revision = "0008_chat_sessions"
branch_labels = None
depends_on = None

job_status = sa.Enum("QUEUED", "RUNNING", "RETRYING", "SUCCEEDED", "FAILED", name="job_status")


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE", name="fk_ingestion_jobs_document_id_documents"),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_celery_task_id", "ingestion_jobs", ["celery_task_id"], unique=True)


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    job_status.drop(op.get_bind(), checkfirst=True)
