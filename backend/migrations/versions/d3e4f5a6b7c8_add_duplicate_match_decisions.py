"""add canonical item aliases and duplicate match decisions

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


duplicate_match_status = postgresql.ENUM(
    "pending", "merged", "kept_separate", name="duplicate_match_status", create_type=False
)


def upgrade() -> None:
    duplicate_match_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "clothing_items",
        sa.Column("canonical_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_clothing_items_canonical_item_id",
        "clothing_items",
        "clothing_items",
        ["canonical_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_clothing_items_canonical_item_id", "clothing_items", ["canonical_item_id"])

    op.create_table(
        "duplicate_match_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_low_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_high_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", duplicate_match_status, nullable=False),
        sa.Column("canonical_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cosine_score", sa.Numeric(6, 5), nullable=True),
        sa.Column("matcher_revision", sa.String(length=100), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("item_low_id <> item_high_id", name="ck_duplicate_match_distinct_items"),
        sa.CheckConstraint("item_low_id < item_high_id", name="ck_duplicate_match_ordered_items"),
        sa.ForeignKeyConstraint(["canonical_item_id"], ["clothing_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_high_id"], ["clothing_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_low_id"], ["clothing_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_low_id", "item_high_id", name="uq_duplicate_match_item_pair"),
    )
    op.create_index(
        "ix_duplicate_match_candidates_user_id",
        "duplicate_match_candidates",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_duplicate_match_candidates_user_id", table_name="duplicate_match_candidates")
    op.drop_table("duplicate_match_candidates")
    op.drop_index("ix_clothing_items_canonical_item_id", table_name="clothing_items")
    op.drop_constraint("fk_clothing_items_canonical_item_id", "clothing_items", type_="foreignkey")
    op.drop_column("clothing_items", "canonical_item_id")
    duplicate_match_status.drop(op.get_bind(), checkfirst=True)
