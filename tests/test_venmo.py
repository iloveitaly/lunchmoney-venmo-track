import pytest

from lunchmoney_venmo_track.venmo import process_venmo_transactions

from tests.conftest import create_mock_transaction


def test_process_venmo_zero_balance(mock_venmo_client):
    """Test that nothing happens when balance is zero."""
    mock_venmo_client.my_profile.return_value.balance = 0

    process_venmo_transactions(token="fake-token")

    # Verify no transactions were fetched
    mock_venmo_client.user.get_user_transactions.assert_not_called()


def test_process_venmo_dry_run(mock_venmo_client):
    """Test dry run mode initiates no transfers."""
    # Setup transactions: 1 income ($20), 1 expense ($10)
    income = create_mock_transaction("t1", 2000, "Lunch", True, "Friend1")
    expense = create_mock_transaction("t2", 1000, "Dinner", False, "Friend2")

    mock_venmo_client.user.get_user_transactions.return_value = [income, expense]

    process_venmo_transactions(token="fake-token", dry_run=True)

    # Verify transfers were NOT initiated
    mock_venmo_client.transfer.initiate_transfer.assert_not_called()


def test_process_venmo_cashout_income(mock_venmo_client):
    """Test cashing out income transactions matching balance."""
    # Balance $50. Income: $20, $30. Total $50. Match!
    mock_venmo_client.my_profile.return_value.balance = 5000

    t1 = create_mock_transaction("t1", 2000, "A", True, "P1")
    t2 = create_mock_transaction("t2", 3000, "B", True, "P2")

    mock_venmo_client.user.get_user_transactions.return_value = [t1, t2]

    process_venmo_transactions(token="fake-token")

    # Should call initiate_transfer twice: once for 2000, once for 3000
    assert mock_venmo_client.transfer.initiate_transfer.call_count == 2
    mock_venmo_client.transfer.initiate_transfer.assert_any_call(amount=2000)
    mock_venmo_client.transfer.initiate_transfer.assert_any_call(amount=3000)


def test_process_venmo_allow_remaining(mock_venmo_client):
    """Test cashing out remaining balance when allow_remaining is True."""
    # Balance $50. Income: $20. Remaining: $30.
    mock_venmo_client.my_profile.return_value.balance = 5000

    t1 = create_mock_transaction("t1", 2000, "A", True, "P1")

    mock_venmo_client.user.get_user_transactions.return_value = [t1]

    process_venmo_transactions(token="fake-token", allow_remaining=True)

    # Should transfer $20 (transaction) AND $30 (remaining)
    assert mock_venmo_client.transfer.initiate_transfer.call_count == 2
    mock_venmo_client.transfer.initiate_transfer.assert_any_call(amount=2000)
    mock_venmo_client.transfer.initiate_transfer.assert_any_call(amount=3000)


def test_process_venmo_skip_remaining(mock_venmo_client):
    """Test skipping cashout if remaining balance exists but allow_remaining is False."""
    # Balance $50. Income: $20. Remaining: $30.
    mock_venmo_client.my_profile.return_value.balance = 5000

    t1 = create_mock_transaction("t1", 2000, "A", True, "P1")

    mock_venmo_client.user.get_user_transactions.return_value = [t1]

    process_venmo_transactions(token="fake-token", allow_remaining=False)

    # Should NOT transfer anything because there is a remainder
    mock_venmo_client.transfer.initiate_transfer.assert_not_called()


def test_process_venmo_db_recording(mock_venmo_client, memory_db_path):
    """Test that transactions are recorded in the database."""
    t1 = create_mock_transaction("t1", 2000, "Note", True, "Payer")
    mock_venmo_client.user.get_user_transactions.return_value = [t1]
    mock_venmo_client.my_profile.return_value.balance = 2000

    process_venmo_transactions(token="fake-token", db_path=memory_db_path)

    import sqlite3

    conn = sqlite3.connect(memory_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT transaction_id, amount, note FROM seen_transactions")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0] == ("t1", 2000, "Note")


def test_process_venmo_ignore_seen_expense(mock_venmo_client, memory_db_path):
    """Test that previously seen expense transactions are ignored."""
    # Pre-populate DB with 't_old'
    import sqlite3

    conn = sqlite3.connect(memory_db_path)
    conn.execute(
        "CREATE TABLE seen_transactions (id INTEGER PRIMARY KEY, transaction_id TEXT, transaction_type TEXT, amount INT, note TEXT, target_actor TEXT, lunchmoney_transaction_id INT, date_created TEXT, payment_date TEXT)"
    )
    conn.execute(
        "INSERT INTO seen_transactions (transaction_id, transaction_type) VALUES ('t_old', 'expense')"
    )
    conn.commit()
    conn.close()

    t_old = create_mock_transaction("t_old", 1000, "Old", False, "Payee")
    t_new = create_mock_transaction("t_new", 1000, "New", False, "Payee")

    mock_venmo_client.user.get_user_transactions.return_value = [t_old, t_new]
    # Set balance to 0 so we don't trigger the "remaining balance" exit
    mock_venmo_client.my_profile.return_value.balance = 0

    process_venmo_transactions(token="fake-token", db_path=memory_db_path)

    # We should only see 't_new' being added to the DB (total 2 rows now)
    conn = sqlite3.connect(memory_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM seen_transactions")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 2  # 1 initial + 1 new


def test_lm_validation():
    """Test validation of Lunch Money arguments."""
    with pytest.raises(ValueError, match="db_path must be specified"):
        process_venmo_transactions(token="t", lunchmoney_token="lm")

    with pytest.raises(
        ValueError, match="Both lunchmoney_token and lunchmoney_category"
    ):
        process_venmo_transactions(token="t", db_path="db", lunchmoney_token="lm")
