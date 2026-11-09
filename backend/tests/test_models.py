"""Focused metadata tests for the first SQLAlchemy models."""

from sqlalchemy import Numeric

from app.db.base import Base
from app.models import Transaction, User


def test_models_are_registered_in_base_metadata():
    assert Base.metadata.tables.keys() >= {"users", "transactions"}


def test_user_schema_constraints():
    table = User.__table__

    assert table.c.id.primary_key
    assert not table.c.email.nullable
    assert any(
        constraint.name == "uq_users_email"
        for constraint in table.constraints
    )
    assert any(index.name == "ix_users_email" for index in table.indexes)
    assert not table.c.password_hash.nullable
    assert table.c.is_active.server_default is not None


def test_transaction_schema_and_relationship():
    table = Transaction.__table__

    assert table.c.user_id.foreign_keys
    assert table.c.amount.type.precision == 12
    assert table.c.amount.type.scale == 2
    assert isinstance(table.c.amount.type, Numeric)
    assert not table.c.occurred_at.nullable
    assert table.c.description.nullable
    assert "ix_transactions_user_id_created_at" in {index.name for index in table.indexes}
    assert Transaction.user.property.back_populates == "transactions"
    assert User.transactions.property.back_populates == "user"
