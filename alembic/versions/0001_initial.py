"""Initial application schema.

Revision ID: 0001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

role = sa.Enum("ADMIN", "MANAGER", "EMPLOYEE", name="user_role")
document_type = sa.Enum("PDF", "MARKDOWN", "SLACK_JSON", name="document_type")
document_status = sa.Enum("UPLOADED", "PROCESSING", "READY", "FAILED", name="document_status")


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_users_department_id_departments"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "documents",
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_documents_department_id_departments"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name="fk_documents_uploaded_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
    )
    for column in ("content_sha256", "department_id", "status", "uploaded_by"):
        op.create_index(f"ix_documents_{column}", "documents", [column])
    op.create_table(
        "chat_messages",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_messages_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("departments")
    document_status.drop(op.get_bind(), checkfirst=True)
    document_type.drop(op.get_bind(), checkfirst=True)
    role.drop(op.get_bind(), checkfirst=True)
