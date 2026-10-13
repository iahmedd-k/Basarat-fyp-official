"""Add an index for paginated user alert queries."""

from typing import Union

from alembic import op

revision: str = "w3x4y5z6a8"
down_revision: Union[str, None] = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_alerts_user_created_at",
        "alerts",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_user_created_at", table_name="alerts")
