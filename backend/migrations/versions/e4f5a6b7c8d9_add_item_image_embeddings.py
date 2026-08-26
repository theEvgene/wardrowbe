"""add versioned per-image embeddings

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_image_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_image_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("model_revision", sa.String(length=100), nullable=False),
        sa.Column("preprocess_revision", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["item_id"], ["clothing_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_image_id"], ["item_images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_image_embeddings_user_id", "item_image_embeddings", ["user_id"])
    op.create_index(
        "uq_item_primary_embedding_version",
        "item_image_embeddings",
        ["item_id", "model", "model_revision", "preprocess_revision"],
        unique=True,
        postgresql_where=sa.text("item_image_id IS NULL"),
    )
    op.create_index(
        "uq_item_additional_embedding_version",
        "item_image_embeddings",
        ["item_image_id", "model", "model_revision", "preprocess_revision"],
        unique=True,
        postgresql_where=sa.text("item_image_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_item_additional_embedding_version", table_name="item_image_embeddings")
    op.drop_index("uq_item_primary_embedding_version", table_name="item_image_embeddings")
    op.drop_index("ix_item_image_embeddings_user_id", table_name="item_image_embeddings")
    op.drop_table("item_image_embeddings")
