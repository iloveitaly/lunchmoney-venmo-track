import sqlite3
import time
import pytest
from unittest.mock import MagicMock
from venmo_api import Transaction, User

@pytest.fixture
def mock_venmo_client(mocker):
    """Mock the Venmo Client."""
    mock_client_cls = mocker.patch("lunchmoney_venmo_track.venmo.Client")
    mock_client = mock_client_cls.return_value
    
    # Setup default profile
    mock_profile = MagicMock()
    mock_profile.username = "me"
    mock_profile.balance = 5000  # $50.00
    mock_client.my_profile.return_value = mock_profile
    
    # Setup transfer object
    mock_client.transfer = MagicMock()
    
    return mock_client

@pytest.fixture
def mock_lunch_money(mocker):
    """Mock the LunchMoney client."""
    mock_lm_cls = mocker.patch("lunchmoney_venmo_track.lunchmoney.LunchMoney")
    return mock_lm_cls.return_value

@pytest.fixture
def memory_db_path(tmp_path):
    """Create a temporary SQLite database file and return its path."""
    db_path = tmp_path / "test_transactions.db"
    return str(db_path)

@pytest.fixture
def memory_db(memory_db_path):
    """Create an in-memory SQLite database connection."""
    conn = sqlite3.connect(memory_db_path)
    # Create the table as expected by the application
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT NOT NULL,
            transaction_id TEXT NOT NULL,
            amount INT NOT NULL,
            note TEXT NOT NULL,
            target_actor TEXT NOT NULL,
            lunchmoney_transaction_id INT,
            date_created TEXT DEFAULT (datetime('now')),
            payment_date TEXT
        );
        """
    )
    yield conn
    conn.close()

def create_mock_transaction(
    id: str, 
    amount: int, 
    note: str, 
    is_income: bool,
    actor_name: str
):
    """Helper to create a mock Venmo Transaction."""
    t = MagicMock(spec=Transaction)
    t.id = id
    t.amount = amount
    t.note = note
    
    # Set payer/payee based on direction
    me_user = MagicMock(spec=User)
    me_user.username = "me"
    me_user.display_name = "My Name"
    
    other_user = MagicMock(spec=User)
    other_user.username = "other"
    other_user.display_name = actor_name
    
    if is_income:
        t.payer = other_user
        t.payee = me_user
    else:
        t.payer = me_user
        t.payee = other_user

    t.date_completed = int(time.time())
    t.date_created = int(time.time())

    return t
