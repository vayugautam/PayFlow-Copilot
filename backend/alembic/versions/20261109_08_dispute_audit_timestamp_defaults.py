"""add server defaults for dispute and audit timestamps

Revision ID: 20261109_08
Revises: 20261109_07
"""

from alembic import op


revision = "20261109_08"
down_revision = "20261109_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE disputes ALTER COLUMN created_at SET DEFAULT now()")
    op.execute("ALTER TABLE disputes ALTER COLUMN updated_at SET DEFAULT now()")
    op.execute("ALTER TABLE audit_logs ALTER COLUMN created_at SET DEFAULT now()")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_logs ALTER COLUMN created_at DROP DEFAULT")
    op.execute("ALTER TABLE disputes ALTER COLUMN updated_at DROP DEFAULT")
    op.execute("ALTER TABLE disputes ALTER COLUMN created_at DROP DEFAULT")
