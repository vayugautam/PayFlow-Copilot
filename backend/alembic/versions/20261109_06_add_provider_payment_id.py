"""track verified provider payments

Revision ID: 20261109_06
Revises: 20261109_05
"""

from alembic import op
import sqlalchemy as sa


revision = "20261109_06"
down_revision = "20261109_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("provider_payment_id", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_transactions_provider_payment_id",
        "transactions",
        ["provider_payment_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transactions_provider_payment_id",
        "transactions",
        type_="unique",
    )
    op.drop_column("transactions", "provider_payment_id")
