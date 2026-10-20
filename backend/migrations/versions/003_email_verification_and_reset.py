"""Add email verification metadata and one-time account recovery tokens.

Revision ID: 003_email_verification_and_reset
Revises: 002_shared_auth_rate_limits
"""
from alembic import op
import sqlalchemy as sa

revision = "003_email_verification_and_reset"
down_revision = "002_shared_auth_rate_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Existing accounts predate verification and must remain able to sign in.
    op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP")

    op.create_table(
        "auth_email_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_email_tokens_user_id", "auth_email_tokens", ["user_id"], unique=False)
    op.create_index("ix_auth_email_tokens_purpose", "auth_email_tokens", ["purpose"], unique=False)
    op.create_index("ix_auth_email_tokens_token_hash", "auth_email_tokens", ["token_hash"], unique=True)
    op.create_index("ix_auth_email_tokens_expires_at", "auth_email_tokens", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_email_tokens_expires_at", table_name="auth_email_tokens")
    op.drop_index("ix_auth_email_tokens_token_hash", table_name="auth_email_tokens")
    op.drop_index("ix_auth_email_tokens_purpose", table_name="auth_email_tokens")
    op.drop_index("ix_auth_email_tokens_user_id", table_name="auth_email_tokens")
    op.drop_table("auth_email_tokens")
    op.drop_column("users", "email_verified_at")
