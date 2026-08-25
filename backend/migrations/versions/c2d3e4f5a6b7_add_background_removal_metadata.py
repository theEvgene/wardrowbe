"""add background removal metadata to clothing items

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "clothing_items",
        sa.Column(
            "background_removal",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("clothing_items", "background_removal")
