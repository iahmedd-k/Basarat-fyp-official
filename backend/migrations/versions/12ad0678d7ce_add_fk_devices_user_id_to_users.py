"""add fk devices user_id to users

Revision ID: 12ad0678d7ce
Revises: 7b95f1f02ce7
Create Date: 2026-09-13 04:52:19.682045

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '12ad0678d7ce'
down_revision = '7b95f1f02ce7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_devices_user_id_users", 'devices', 'users', ['user_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint("fk_devices_user_id_users", 'devices', type_='foreignkey')