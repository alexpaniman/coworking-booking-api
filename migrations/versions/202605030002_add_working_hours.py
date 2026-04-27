"""add working hours

Revision ID: 202605030002
Revises: 202605030001
Create Date: 2026-05-04 00:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "202605030002"
down_revision = "202605030001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column("opens_at", sa.Time(), nullable=False, server_default="08:00:00"),
    )
    op.add_column(
        "locations",
        sa.Column("closes_at", sa.Time(), nullable=False, server_default="22:00:00"),
    )
    op.alter_column("locations", "opens_at", server_default=None)
    op.alter_column("locations", "closes_at", server_default=None)


def downgrade() -> None:
    op.drop_column("locations", "closes_at")
    op.drop_column("locations", "opens_at")
