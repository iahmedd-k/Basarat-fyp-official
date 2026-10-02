"""Merge watchlist and device schema heads.

Revision ID: q7r8s9t0u1v2
Revises: o6p7q8r9s0t1, p6q7r8s9t0u1
Create Date: 2026-10-02
"""

from typing import Sequence, Union

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = (
    "o6p7q8r9s0t1",
    "p6q7r8s9t0u1",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass