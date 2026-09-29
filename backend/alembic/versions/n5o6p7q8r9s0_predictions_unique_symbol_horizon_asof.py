"""Deduplicate predictions and enforce unique (symbol, horizon, as_of_date).

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, Sequence[str], None] = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep best row per key: prefer evaluated outcomes, then newest predicted_at/id
    op.execute(
        """
        DELETE FROM predictions
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol, horizon, as_of_date
                           ORDER BY
                               CASE WHEN actual_direction IS NOT NULL THEN 0 ELSE 1 END,
                               predicted_at DESC NULLS LAST,
                               id DESC
                       ) AS rn
                FROM predictions
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_predictions_symbol_horizon_as_of",
        "predictions",
        ["symbol", "horizon", "as_of_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_predictions_symbol_horizon_as_of",
        "predictions",
        type_="unique",
    )
