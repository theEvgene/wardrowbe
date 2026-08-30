"""separate refinement lineage from wore-instead replacements

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a8"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outfits",
        sa.Column("refined_from_outfit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_outfits_refined_from_outfit_id",
        "outfits",
        "outfits",
        ["refined_from_outfit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE outfits
        SET refined_from_outfit_id = replaces_outfit_id,
            replaces_outfit_id = NULL
        WHERE replaces_outfit_id IS NOT NULL
          AND generation_context ? 'refinement'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE outfits
        SET replaces_outfit_id = refined_from_outfit_id
        WHERE refined_from_outfit_id IS NOT NULL
          AND replaces_outfit_id IS NULL
        """
    )
    op.drop_constraint(
        "fk_outfits_refined_from_outfit_id", "outfits", type_="foreignkey"
    )
    op.drop_column("outfits", "refined_from_outfit_id")
