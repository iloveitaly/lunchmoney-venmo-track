from unittest.mock import MagicMock
from lunchmoney_venmo_track.lunchmoney import update_lunchmoney_transactions
from lunchable.models.transactions import TransactionObject

def test_update_lm_category_not_found(memory_db, mock_lunch_money):
    """Test handling when category is not found."""
    mock_lunch_money.get_categories.return_value = []
    
    update_lunchmoney_transactions(memory_db, "token", "MissingCategory")
    
    # Should log error and return (no transactions fetched)
    mock_lunch_money.get_transactions.assert_not_called()

def test_update_lm_matching(memory_db, mock_lunch_money):
    """Test matching a Venmo transaction to a Lunch Money transaction."""
    # Setup Category
    mock_cat = MagicMock()
    mock_cat.name = "Venmo"
    mock_cat.id = 123
    mock_lunch_money.get_categories.return_value = [mock_cat]
    
    # Setup LM Transaction (unmatched)
    lm_txn = MagicMock(spec=TransactionObject)
    lm_txn.id = 999
    lm_txn.amount = -15.00  # Expense
    lm_txn.group_id = None
    lm_txn.notes = None
    mock_lunch_money.get_transactions.return_value = [lm_txn]
    
    # Setup Venmo Record in DB
    # Note: VenmoRecord expects amount in cents (1500)
    memory_db.execute(
        """
        INSERT INTO seen_transactions 
        (transaction_type, transaction_id, amount, note, target_actor, date_created)
        VALUES ('expense', 'v1', 1500, 'Tacos', 'Taqueria', date('now'))
        """
    )
    memory_db.commit()
    
    update_lunchmoney_transactions(memory_db, "token", "Venmo")
    
    # Verify update called
    mock_lunch_money.update_transaction.assert_called_once()
    args, _ = mock_lunch_money.update_transaction.call_args
    assert args[0] == 999
    assert args[1]['payee'] == "Taqueria"
    assert args[1]['notes'] == "Tacos"
    
    # Verify DB updated
    cursor = memory_db.cursor()
    cursor.execute("SELECT lunchmoney_transaction_id FROM seen_transactions WHERE transaction_id='v1'")
    assert cursor.fetchone()[0] == 999

def test_update_lm_no_match(memory_db, mock_lunch_money):
    """Test when no Venmo transaction matches the LM transaction."""
    mock_cat = MagicMock()
    mock_cat.name = "Venmo"
    mock_cat.id = 123
    mock_lunch_money.get_categories.return_value = [mock_cat]
    
    lm_txn = MagicMock(spec=TransactionObject)
    lm_txn.id = 999
    lm_txn.amount = -50.00
    lm_txn.group_id = None
    lm_txn.notes = None
    mock_lunch_money.get_transactions.return_value = [lm_txn]
    
    # DB is empty
    
    update_lunchmoney_transactions(memory_db, "token", "Venmo")
    
    # No update should happen
    mock_lunch_money.update_transaction.assert_not_called()

def test_update_lm_already_linked(memory_db, mock_lunch_money):
    """Test that already linked transactions in DB are ignored."""
    mock_cat = MagicMock()
    mock_cat.name = "Venmo"
    mock_cat.id = 123
    mock_lunch_money.get_categories.return_value = [mock_cat]
    
    lm_txn = MagicMock(spec=TransactionObject)
    lm_txn.id = 888
    lm_txn.amount = -10.00
    lm_txn.group_id = None
    lm_txn.notes = None
    mock_lunch_money.get_transactions.return_value = [lm_txn]
    
    # DB has transaction but it's already linked (lunchmoney_transaction_id IS NOT NULL)
    memory_db.execute(
        """
        INSERT INTO seen_transactions 
        (transaction_type, transaction_id, amount, note, target_actor, lunchmoney_transaction_id, date_created)
        VALUES ('expense', 'v1', 1000, 'Coffee', 'Cafe', 777, date('now'))
        """
    )
    memory_db.commit()
    
    update_lunchmoney_transactions(memory_db, "token", "Venmo")
    
    # Should not match because the query filters WHERE lunchmoney_transaction_id is NULL
    mock_lunch_money.update_transaction.assert_not_called()
