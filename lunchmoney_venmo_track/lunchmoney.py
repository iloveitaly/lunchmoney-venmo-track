from dataclasses import dataclass, fields
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection
from typing import Literal

import structlog
from lunchable import LunchMoney
from lunchable.models.transactions import TransactionObject, TransactionUpdateObject

log = structlog.get_logger()

# How many days back will we try and look for matching transactions? Anything
# older will be ignored forever
CUTOFF_DAYS = 60

# Maximum days between a venmo payment_date and a LM transaction date for a match
DATE_PROXIMITY_DAYS = 5


def update_lunchmoney_transactions(
    db: Connection,
    token: str,
    category_name: str,
):
    """
    Updates lunch money transactions with details from previously tracked venmo
    transactions. Works for both incoming and outgoing venmos.

    This is done by looking up Lunch Money transactions in the provided
    `category_name`. This category should be exclusive for venmo transactions,
    usually by setting up a Lunch Money rule to place venmo income / expenses
    into it. These transactions will then be matched against venmo transacitons
    that have not already had a lunchmoney_transaction_id associated to them in
    the database.
    """

    log.info("updating lunch money transactions", category_name=category_name)

    lunch = LunchMoney(access_token=token)

    try:
        category = next(c for c in lunch.get_categories() if c.name == category_name)
    except StopIteration:
        log.error("cannot find lunch money category", category_name=category_name)
        return

    # Find lunch money transactiosn that haven't been updated
    lm_transactions = [
        transaction
        for transaction in lunch.get_transactions(
            category_id=category.id,
            start_date=(datetime.now(tz=UTC) - timedelta(days=CUTOFF_DAYS)).date(),
            end_date=datetime.now(tz=UTC).date(),
        )
        if
        # Ignore grouped transactions
        transaction.group_id is None
        and
        # Transactions with notes have already been updated
        transaction.notes is None
    ]

    @dataclass
    class VenmoRecord:
        id: int
        transaction_type: Literal["expense", "income"]
        amount: int
        note: str
        target_actor: str
        # ISO date string; rows without payment_date are excluded at query level
        payment_date: str

    columns = [f.name for f in fields(VenmoRecord)]

    # Find transactions that we haven't associated a lunch money transaction,
    # order by rescency so older transactions that were never correctly associated.
    # Exclude rows without payment_date (pre-migration rows can't be date-matched).
    cursor = db.cursor()
    cursor.execute(
        f"""
        SELECT {",".join(columns)}
        FROM seen_transactions
        WHERE
            lunchmoney_transaction_id is NULL AND
            date_created > date('now', '-{CUTOFF_DAYS} day') AND
            payment_date IS NOT NULL
        ORDER BY date_created DESC"""
    )
    venmo_transactions = [VenmoRecord(*row) for row in cursor.fetchall()]

    # Track how many transactions we were able to match
    matched_transactions: list[tuple[VenmoRecord, TransactionObject]] = []

    # Update lunch money and venmo transaction records
    for lm_txn in lm_transactions:
        amount = int(Decimal(str(abs(lm_txn.amount))) * 100)

        # Match by amount only — sign from Plaid/bank sync is not a reliable
        # proxy for venmo P2P direction (both income and expense can appear as
        # the same sign depending on the account).
        candidates = [v for v in venmo_transactions if v.amount == amount]

        if not candidates:
            continue

        lm_date = lm_txn.date
        closest = min(
            candidates,
            key=lambda v: abs((date.fromisoformat(v.payment_date) - lm_date).days),
        )
        closest_date = date.fromisoformat(closest.payment_date)

        if abs((closest_date - lm_date).days) > DATE_PROXIMITY_DAYS:
            continue

        matching_venmo = closest

        # Remove the consued venmo transaction
        venmo_transactions.remove(matching_venmo)

        matched_transactions.append((matching_venmo, lm_txn))

        # Update transaction in lunch money
        # TransactionUpdateObject uses Field(None) in lunchable which pyright flags as missing arguments if called directly
        update = TransactionUpdateObject.model_validate(
            {
                "payee": matching_venmo.target_actor,
                "notes": matching_venmo.note,
            }
        )
        lunch.update_transaction(lm_txn.id, update)

        # Record lunch money transaction ID
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE seen_transactions SET lunchmoney_transaction_id=? WHERE id=?
            """,
            (lm_txn.id, matching_venmo.id),
        )
        db.commit()

    log.info(
        "lunch money updates completed",
        matched_count=len(matched_transactions),
        total_unlinked_lm_transactions=len(lm_transactions),
    )

    for venmo_txn, lm_txn in matched_transactions:
        log.info(
            "transaction matched",
            venmo_actor=venmo_txn.target_actor,
            venmo_note=venmo_txn.note,
            lunchmoney_transaction_id=lm_txn.id,
        )
