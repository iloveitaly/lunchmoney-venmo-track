from datetime import date
from decimal import Decimal
from sqlite3 import Connection
from typing import Literal

import structlog
from lunchmoney import (
    ApiClient,
    CategoriesApi,
    CategoryObject,
    Configuration,
    TransactionObject,
    TransactionsApi,
    TransactionsBulkApi,
    UpdateTransactionObject,
)
from pydantic import BaseModel
from whenever import Date

log = structlog.get_logger()

# How many days back will we try and look for matching transactions? Anything
# older will be ignored forever
CUTOFF_DAYS = 60

# Maximum days between a venmo payment_date and a LM transaction date for a match
DATE_PROXIMITY_DAYS = 5


class LunchMoney:
    """Lunch Money API client wrapping lunchmoney-python API classes."""

    def __init__(self, access_token: str, client: ApiClient | None = None):
        self.configuration = Configuration(access_token=access_token)
        self.client = client or ApiClient(self.configuration)
        self.categories_api = CategoriesApi(self.client)
        self.transactions_api = TransactionsApi(self.client)
        self.transactions_bulk_api = TransactionsBulkApi(self.client)

    def get_categories(self) -> list[CategoryObject]:
        response = self.categories_api.get_all_categories(format="flattened")
        return response.categories or []

    def get_transactions(
        self,
        category_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TransactionObject]:
        response = self.transactions_bulk_api.get_all_transactions(
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
        )
        return response.transactions or []

    def update_transaction(
        self,
        transaction_id: int,
        update: UpdateTransactionObject,
    ) -> TransactionObject:
        return self.transactions_api.update_transaction(
            id=transaction_id,
            update_transaction_object=update,
        )


class VenmoRecord(BaseModel):
    id: int
    transaction_type: Literal["expense", "income"]
    amount: int
    note: str
    target_actor: str
    # ISO date string; rows without payment_date are excluded at query level
    payment_date: str


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
    today = Date.today_in_system_tz()
    start_date = today.add(days=-CUTOFF_DAYS).to_stdlib()
    end_date = today.to_stdlib()

    transactions = lunch.get_transactions(
        category_id=category.id,
        start_date=start_date,
        end_date=end_date,
    )

    lm_transactions = []
    for transaction in transactions:
        is_grouped = (
            getattr(transaction, "group_parent_id", None) is not None
            or getattr(transaction, "group_id", None) is not None
            or getattr(transaction, "is_group_parent", False)
        )
        if is_grouped:
            # Ignore grouped transactions
            continue

        if transaction.notes is not None:
            # Transactions with notes have already been updated
            continue

        lm_transactions.append(transaction)

    columns = list(VenmoRecord.model_fields.keys())

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
    venmo_transactions = [
        VenmoRecord.model_validate(dict(zip(columns, row)))
        for row in cursor.fetchall()
    ]

    # Track how many transactions we were able to match
    matched_transactions: list[tuple[VenmoRecord, TransactionObject]] = []

    # Update lunch money and venmo transaction records
    for lm_txn in lm_transactions:
        amount = int(abs(Decimal(str(lm_txn.amount))) * 100)

        # Match by amount only — sign from Plaid/bank sync is not a reliable
        # proxy for venmo P2P direction (both income and expense can appear as
        # the same sign depending on the account).
        candidates = [v for v in venmo_transactions if v.amount == amount]

        if not candidates:
            continue

        lm_date = getattr(lm_txn, "var_date", None) or getattr(lm_txn, "date", None)
        assert lm_date is not None
        target_date: date = lm_date

        closest = min(
            candidates,
            key=lambda v: abs((date.fromisoformat(v.payment_date) - target_date).days),
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
        update = UpdateTransactionObject(
            payee=matching_venmo.target_actor,
            notes=matching_venmo.note,
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
