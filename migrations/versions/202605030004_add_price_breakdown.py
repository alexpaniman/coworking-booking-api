"""add price breakdown

Revision ID: 202605030004
Revises: 202605030003
Create Date: 2026-05-04 00:50:00
"""
from alembic import op
import sqlalchemy as sa


revision = "202605030004"
down_revision = "202605030003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("price_breakdown", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "price_breakdown")
