"""Add Markdown heading and source-line metadata.

Revision ID: 0003_markdown_metadata
Revises: 0002_document_chunks
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_markdown_metadata"
down_revision = "0002_document_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("document_chunks", "page", existing_type=sa.Integer(), nullable=True)
    op.add_column("document_chunks", sa.Column("heading_path", postgresql.JSONB(), nullable=True))
    op.add_column("document_chunks", sa.Column("line_start", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("line_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    if op.get_bind().execute(
        sa.text("SELECT 1 FROM document_chunks WHERE page IS NULL LIMIT 1")
    ).first():
        raise RuntimeError("Cannot downgrade while Markdown chunks with NULL pages exist")
    op.drop_column("document_chunks", "line_end")
    op.drop_column("document_chunks", "line_start")
    op.drop_column("document_chunks", "heading_path")
    op.alter_column("document_chunks", "page", existing_type=sa.Integer(), nullable=False)
