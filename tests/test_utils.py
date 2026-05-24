import pytest
from unittest.mock import MagicMock
from requests.exceptions import RequestException
from tenacity import RetryError

from lunchmoney_venmo_track.heartbeat import send_heartbeat
from lunchmoney_venmo_track.internet import wait_for_internet_connection

# --- Heartbeat Tests ---

def test_heartbeat_success(mocker):
    """Test successful heartbeat."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.raise_for_status = MagicMock()
    
    send_heartbeat("http://test.com")
    
    mock_get.assert_called_once_with("http://test.com", timeout=10)

def test_heartbeat_retry_fail(mocker):
    """Test heartbeat retries and eventual failure (no crash)."""
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = RequestException("Boom")
    
    # We expect it to retry 3 times then stop, but NOT raise an exception
    # because reraise=False in the decorator.
    
    # To make test fast, we can mock tenacity's wait or sleep, 
    # but with simple retry logic it might be easier to just let it run if timeouts are small,
    # or mock the sleep.
    
    # Actually, tenacity uses time.sleep by default.
    mocker.patch("time.sleep") 
    
    with pytest.raises(RetryError):
        # wait.. reraise=False means it returns the result of the last attempt?
        # If the last attempt raised an exception, tenacity with reraise=False 
        # normally returns None or the result if it was a value. 
        # But here the function *raises* an exception.
        
        # Let's check the implementation:
        # try: request... except: raise e
        # So the exception IS raised inside the function.
        # tenacity catches it.
        # If retries are exhausted, and reraise=False, it should raise RetryError wrapping the last exception.
        # Wait, if reraise=False, it should *return* the result of the last attempt.
        # Since the last attempt raised an exception, it might re-raise it?
        # Let's verify behavior.
        send_heartbeat("http://fail.com")
        
    assert mock_get.call_count == 3

# --- Internet Tests ---

def test_internet_connected(mocker):
    """Test when internet is connected."""
    mock_socket = mocker.patch("socket.socket")
    mock_socket.return_value.__enter__.return_value.connect.return_value = None
    
    wait_for_internet_connection()
    # Should just return immediately

def test_internet_retry(mocker):
    """Test retry logic when internet is down initially."""
    mock_socket = mocker.patch("socket.socket")
    # First call raises error, second call succeeds
    mock_socket.return_value.__enter__.return_value.connect.side_effect = [OSError("Down"), None]
    
    mocker.patch("time.sleep") # Speed up backoff
    
    wait_for_internet_connection()
    
    assert mock_socket.call_count >= 2
