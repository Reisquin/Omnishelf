"""Add shared database-backed authentication rate limits.

Revision ID: 002_shared_auth_rate_limits
Revises: 001_initial_backend
"""
from alembic import op
import sqlalchemy as sa

revision = "002_shared_auth_rate_limits"
down_revision = "001_initial_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limits",
        sa.Column("action", sa.String(length=16), primary_key=True, nullable=False),
        sa.Column("client_key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("window_started", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_auth_rate_limits_window_started",
        "auth_rate_limits",
        ["window_started"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limits_window_started", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
