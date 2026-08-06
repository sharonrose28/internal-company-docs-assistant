"""Add multi-session conversational memory.

Revision ID: 0008_chat_sessions
Revises: 0007_audit_events
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_chat_sessions"
down_revision = "0007_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_chat_sessions_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.add_column("chat_messages", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(sa.text("""
        INSERT INTO chat_sessions (id, user_id, title)
        SELECT md5('legacy-chat-session:' || user_id::text)::uuid, user_id, 'Previous conversation'
        FROM chat_messages
        GROUP BY user_id
    """))
    op.execute(sa.text("""
        UPDATE chat_messages
        SET session_id = md5('legacy-chat-session:' || user_id::text)::uuid
        WHERE session_id IS NULL
    """))
    op.alter_column("chat_messages", "session_id", nullable=False)
    op.create_foreign_key(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages", "chat_sessions", ["session_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index(
        "ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_constraint("fk_chat_messages_session_id_chat_sessions", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "session_id")
    op.drop_table("chat_sessions")
