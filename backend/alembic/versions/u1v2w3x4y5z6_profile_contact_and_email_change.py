"""Add profile contact fields and pending email-change state."""

from alembic import op
import sqlalchemy as sa


revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column(
        "email_verification_tokens",
        sa.Column("pending_email", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_email_verification_tokens_pending_email",
        "email_verification_tokens",
        ["pending_email"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_pending_email", table_name="email_verification_tokens")
    op.drop_column("email_verification_tokens", "pending_email")
    op.drop_column("users", "phone")
