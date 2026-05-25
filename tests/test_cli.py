from click.testing import CliRunner
from lunchmoney_venmo_track.cli import cli

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Automatically cash-out your Venmo balance" in result.output

def test_cli_missing_args(monkeypatch):
    monkeypatch.delenv("VENMO_API_TOKEN", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code != 0
    assert "Missing option '--token'" in result.output

def test_cli_success(mocker):
    """Test successful CLI run with mocks."""
    mock_process = mocker.patch("lunchmoney_venmo_track.cli.process_venmo_transactions")
    mocker.patch("lunchmoney_venmo_track.cli.send_heartbeat")
    
    # Mock sys.stdin.isatty to avoid internet check
    mocker.patch("sys.stdin.isatty", return_value=True)
    
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--token", "mytoken",
        "--allow-remaining",
        "--dry-run"
    ])
    
    assert result.exit_code == 0
    mock_process.assert_called_once()
    args = mock_process.call_args[1]
    assert args['token'] == "mytoken"
    assert args['dry_run'] is True
    assert args['allow_remaining'] is True

def test_cli_env_vars(mocker):
    """Test CLI picks up environment variables."""
    mock_process = mocker.patch("lunchmoney_venmo_track.cli.process_venmo_transactions")
    mocker.patch("sys.stdin.isatty", return_value=True)
    
    runner = CliRunner()
    env = {
        "VENMO_API_TOKEN": "envtoken",
        "TRANSACTION_DB": "envdb.db"
    }
    
    result = runner.invoke(cli, [], env=env)
    
    assert result.exit_code == 0
    mock_process.assert_called_once()
    assert mock_process.call_args[1]['token'] == "envtoken"
    assert mock_process.call_args[1]['db_path'] == "envdb.db"
