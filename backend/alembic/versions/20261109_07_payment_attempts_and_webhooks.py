"""persist Razorpay orders, attempts, and webhook deliveries

Revision ID: 20261109_07
Revises: 20261109_06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261109_07"
down_revision = "20261109_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("provider_order_id", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("failure_description", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("failure_source", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("failure_step", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("failure_reason", sa.String(255), nullable=True))

    op.create_table(
        "payment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_order_id", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_order_id"),
    )
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_event_id", sa.String(150), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id"),
    )


def downgrade() -> None:
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_orders")
    op.drop_column("transactions", "failure_reason")
    op.drop_column("transactions", "failure_step")
    op.drop_column("transactions", "failure_source")
    op.drop_column("transactions", "failure_description")
    op.drop_column("transactions", "provider_order_id")
