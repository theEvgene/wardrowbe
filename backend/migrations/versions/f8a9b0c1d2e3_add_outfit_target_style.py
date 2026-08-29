"""add target style to outfits

Revision ID: f8a9b0c1d2e3
Revises: b7c8d9e0f1a2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outfits", sa.Column("target_style", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("outfits", "target_style")
