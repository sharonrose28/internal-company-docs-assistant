"""Add Slack conversation metadata.

Revision ID: 0004_slack_metadata
Revises: 0003_markdown_metadata
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_slack_metadata"
down_revision = "0003_markdown_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("channel", sa.String(255), nullable=True))
    op.add_column("document_chunks", sa.Column("thread", sa.String(64), nullable=True))
    op.add_column("document_chunks", sa.Column("participants", postgresql.JSONB(), nullable=True))
    op.create_index("ix_document_chunks_channel", "document_chunks", ["channel"])
    op.create_index("ix_document_chunks_thread", "document_chunks", ["thread"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_thread", table_name="document_chunks")
    op.drop_index("ix_document_chunks_channel", table_name="document_chunks")
    op.drop_column("document_chunks", "participants")
    op.drop_column("document_chunks", "thread")
    op.drop_column("document_chunks", "channel")
