"""Seed idempotent development-only demo transactions.

Usage:
    Set DEMO_USER_PASSWORD in the environment, then run:
    python scripts/seed_demo_transactions.py

The script targets the configured development DATABASE_URL and only touches
the dedicated demo user and its transactions.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, engine
from app.models import Transaction, User

DEMO_EMAIL = "demo@payflow.local"


async def seed() -> int:
    password = os.environ.get("DEMO_USER_PASSWORD")
    if not password:
        raise RuntimeError("DEMO_USER_PASSWORD must be set; no demo password is hardcoded")

    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=get_password_hash(password))
            db.add(user)
            await db.flush()

        existing = await db.scalars(
            select(Transaction).where(Transaction.user_id == user.id)
        )
        existing_by_key = {(item.merchant, item.status): item for item in existing}
        now = datetime.now(timezone.utc)
        # These are application-defined simulated codes, not processor or
        # network codes. Numeric processor codes are avoided because their
        # meanings vary across payment networks.
        records = [
            ("Acme Coffee", "successful", None, "card", Decimal("12.50")),
            ("Contoso Market", "failed", "INSUFFICIENT_FUNDS", "card", Decimal("84.99")),
            ("Globex Travel", "pending", None, "bank_transfer", Decimal("240.00")),
            ("Initech Media", "refunded", None, "card", Decimal("19.99")),
        ]
        for index, (merchant, status, failure_code, payment_method, amount) in enumerate(records):
            existing_transaction = existing_by_key.get((merchant, status))
            if existing_transaction is not None:
                # Repair older demo rows that used unsupported numeric codes.
                if existing_transaction.failure_code != failure_code:
                    existing_transaction.failure_code = failure_code
                continue
            db.add(
                Transaction(
                    user_id=user.id,
                    amount=amount,
                    currency="USD",
                    status=status,
                    merchant=merchant,
                    description="Development demo transaction",
                    failure_code=failure_code,
                    payment_method=payment_method,
                    occurred_at=now - timedelta(days=index),
                )
            )
        await db.commit()
        print(f"Seeded demo data for {DEMO_EMAIL}")
    await engine.dispose()
    return 0


def main() -> None:
    if sys.platform == "win32":
        asyncio.run(seed(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(seed())


if __name__ == "__main__":
    main()
