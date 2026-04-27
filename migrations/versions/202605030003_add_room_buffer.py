"""add room buffer

Revision ID: 202605030003
Revises: 202605030002
Create Date: 2026-05-04 00:40:00
"""
from alembic import op
import sqlalchemy as sa


revision = "202605030003"
down_revision = "202605030002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("rooms", "buffer_minutes", server_default=None)


def downgrade() -> None:
    op.drop_column("rooms", "buffer_minutes")
