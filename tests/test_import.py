"""Test lunchmoney-venmo-track."""

import lunchmoney_venmo_track


def test_import() -> None:
    """Test that the  can be imported."""
    assert isinstance(lunchmoney_venmo_track.__name__, str)


def test_version() -> None:
    """Test that the version is available."""
    assert isinstance(lunchmoney_venmo_track.__version__, str)
