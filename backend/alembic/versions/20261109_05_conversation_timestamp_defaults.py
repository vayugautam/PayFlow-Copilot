"""repair conversation timestamp defaults

Revision ID: 20261109_05
Revises: 20261108_04
"""

from alembic import op


revision = "20261109_05"
down_revision = "20261108_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Revision 03 declared the timestamp columns NOT NULL but omitted their
    # PostgreSQL defaults. Existing applications can therefore fail when the
    # ORM relies on the model's server_default declaration during INSERT.
    op.execute("ALTER TABLE conversations ALTER COLUMN created_at SET DEFAULT now()")
    op.execute("ALTER TABLE conversations ALTER COLUMN updated_at SET DEFAULT now()")


def downgrade() -> None:
    op.execute("ALTER TABLE conversations ALTER COLUMN created_at DROP DEFAULT")
    op.execute("ALTER TABLE conversations ALTER COLUMN updated_at DROP DEFAULT")
