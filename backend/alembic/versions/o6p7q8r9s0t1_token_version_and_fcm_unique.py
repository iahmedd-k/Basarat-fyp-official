"""Add user.token_version and unique devices.fcm_token

Revision ID: o6p7q8r9s0t1
Revises: 1b3be1928fad
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o6p7q8r9s0t1"
down_revision: Union[str, Sequence[str], None] = "1b3be1928fad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        """
        DELETE FROM devices d
        USING devices newer
        WHERE d.fcm_token = newer.fcm_token
          AND d.created_at < newer.created_at
        """
    )
    op.create_unique_constraint("uq_devices_fcm_token", "devices", ["fcm_token"])
    op.create_index("ix_devices_fcm_token", "devices", ["fcm_token"])


def downgrade() -> None:
    op.drop_index("ix_devices_fcm_token", table_name="devices")
    op.drop_constraint("uq_devices_fcm_token", "devices", type_="unique")
    op.drop_column("users", "token_version")