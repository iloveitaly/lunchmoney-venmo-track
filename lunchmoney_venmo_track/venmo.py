import sqlite3
from datetime import datetime
from typing import Any, List, Optional, Union

from venmo_api import Client, Transaction

from lunchmoney_venmo_track.lunchmoney import update_lunchmoney_transactions


def process_venmo_transactions(
    token: str,
    db_path: Optional[str] = None,
    lunchmoney_token: Optional[str] = None,
    lunchmoney_category: Optional[str] = None,
    dry_run: bool = False,
    allow_remaining: bool = False,
    quiet: bool = False,
    output_func: Optional[Any] = None,
):
    """
    Process Venmo transactions: cash out balance and sync with Lunch Money.
    """

    if output_func is None:

        def output(msg: str) -> None:
            if not quiet:
                print(msg)
    else:
        output = output_func

    if lunchmoney_token and not db_path:
        raise ValueError("db_path must be specified to use the LM integration")

    if (lunchmoney_token is None) != (lunchmoney_category is None):
        raise ValueError(
            "Both lunchmoney_token and lunchmoney_category are required for LM integration"
        )

    db: Optional[sqlite3.Connection] = None

    # Setup transactions table
    if db_path is not None:
        db = sqlite3.connect(db_path)
        db.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS seen_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_type TEXT NOT NULL,
                transaction_id TEXT NOT NULL,
                amount INT NOT NULL,
                note TEXT NOT NULL,
                target_actor TEXT NOT NULL,
                lunchmoney_transaction_id INT ,
                date_created TEXT DEFAULT (datetime('now'))
            );"""
        )

    # Get list of know transaction IDs
    seen_transaction_ids: Union[None, List[str]] = None

    if db:
        cursor = db.cursor()
        cursor.execute("SELECT transaction_id FROM seen_transactions")
        seen_transaction_ids = [row[0] for row in cursor.fetchall()]

    # output the date and time so when this is running on a cron we know the last time it was run
    output(f"Running venmo_auto_cashout at {datetime.now()}")

    # Venmo API client
    venmo = Client(access_token=token)

    me = venmo.my_profile()
    if not me:
        raise Exception("Failed to load Venmo profile")

    current_balance: int = me.balance

    if current_balance == 0 and not db:
        output("Your venmo balance is zero. Nothing to do")
        return

    output("Your balance is ${:,.2f}".format(current_balance / 100))

    # XXX: There may be some leftover amount if the transactions do not match
    # up exactly to the current account balance.
    remaining_balance = current_balance

    income_transactions: List[Transaction] = []
    expense_transactions: List[Transaction] = []

    transactions = venmo.user.get_user_transactions(user=me)

    if transactions is None:
        raise Exception("Failed to load transactions")

    # Produce a list of eligible transactions
    for transaction in transactions:
        is_expense = transaction.payee.username != me.username

        # Extract expense transactions we haven't seen yet
        if is_expense:
            if (
                seen_transaction_ids is None
                or transaction.id not in seen_transaction_ids
            ):
                expense_transactions.append(transaction)

        # Only track income transactions until we've exhausted the
        # current balance
        elif transaction.amount <= remaining_balance:
            remaining_balance = remaining_balance - transaction.amount
            income_transactions.append(transaction)

    all_transactions = [*income_transactions, *expense_transactions]
    has_transactions = len(all_transactions) > 0

    # Show some details about what we're about to do
    output(
        "There are {} income transactions to cash-out".format(len(income_transactions))
    )
    output(
        "There are {} expense transactions to track".format(len(expense_transactions))
    )

    if has_transactions or remaining_balance > 0:
        output("")

    for transaction in income_transactions:
        output(
            " -> Income: +${price:,.2f} -- {name} ({note})".format(
                name=transaction.payer.display_name,
                price=transaction.amount / 100,
                note=transaction.note,
            )
        )

    if remaining_balance > 0:
        output(" -> Income: ${:,.2f} of extra balance".format(remaining_balance / 100))

    for transaction in expense_transactions:
        output(
            " -> Expense: -${price:,.2f} -- {name} ({note})".format(
                name=transaction.payee.display_name,
                price=transaction.amount / 100,
                note=transaction.note,
            )
        )

    # Nothing left to do in dry-run mode
    if dry_run:
        output("\ndry-run. Not initiating transfers")
        return

    # Do not cash out if
    if not allow_remaining and remaining_balance > 0:
        output(
            "\nRemaining balance without --allow-remaining. Not initiating transfers"
        )
        return

    # Do the transactions
    for transaction in income_transactions:
        venmo.transfer.initiate_transfer(amount=transaction.amount)

    if remaining_balance > 0:
        venmo.transfer.initiate_transfer(amount=remaining_balance)

    # Update seen expense transaction
    if db:
        query = """
        INSERT INTO seen_transactions
        (transaction_type, transaction_id, amount, note, target_actor)
        VALUES(?, ?, ?, ?, ?)
        """
        records = [
            *[
                ("income", t.id, t.amount, t.note, t.payer.display_name)
                for t in income_transactions
            ],
            *[
                ("expense", t.id, t.amount, t.note, t.payee.display_name)
                for t in expense_transactions
            ],
        ]
        cursor = db.cursor()
        cursor.executemany(query, records)
        db.commit()

    # Update lunchmoney transactions
    if db and lunchmoney_token and lunchmoney_category:
        update_lunchmoney_transactions(
            db,
            lunchmoney_token,
            lunchmoney_category,
            output,
        )

    output("\nAll money transferred out!")
