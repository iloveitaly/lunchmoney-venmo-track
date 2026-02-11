import click
from decouple import config
from structlog_config import configure_logger

from lunchmoney_venmo_track.venmo import process_venmo_transactions

def setup_logging():
    # Read environment variables directly to determine configuration
    json_logging = config("JSON_LOGGING", default=True, cast=bool)
    
    # Configure the logger using structlog-config
    configure_logger(json_logger=json_logging)

@click.command()
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Do not actually initiate bank transfers",
)
@click.option(
    "--allow-remaining/--no-allow-remaining",
    default=config("ALLOW_REMAINING", default=False, cast=bool),
    help="Allow remaining balance to be cashed-out",
)
@click.option(
    "--token",
    envvar="VENMO_API_TOKEN",
    required=True,
    help="Your venmo API token",
)
@click.option(
    "--transaction-db",
    envvar="TRANSACTION_DB",
    help="File to tracks which transactions have been seen. Required for LM integration",
)
@click.option(
    "--lunchmoney-token",
    envvar="LUNCHMONEY_TOKEN",
    help="Enables Lunch Money integration for tracking venmo",
)
@click.option(
    "--lunchmoney-category",
    envvar="LUNCHMONEY_CATEGORY",
    help="The Lunch Money category to look for venmo transactions",
)
def cli(
    dry_run: bool,
    allow_remaining: bool,
    token: str,
    transaction_db: str,
    lunchmoney_token: str,
    lunchmoney_category: str,
):
    """
    Automatically cash-out your Venmo balance as individual transfers
    """
    setup_logging()
    
    if lunchmoney_token and not transaction_db:
        raise click.UsageError("--transaction-db must be specified to use the LM integration")

    if (lunchmoney_token is None) != (lunchmoney_category is None):
        raise click.UsageError("--lunchmoney-token and --lunchmoney-category are both required for LM integration")

    process_venmo_transactions(
        token=token,
        db_path=transaction_db,
        lunchmoney_token=lunchmoney_token,
        lunchmoney_category=lunchmoney_category,
        dry_run=dry_run,
        allow_remaining=allow_remaining,
    )

    click.secho("\nAll Venmo transactions processed successfully!", fg="green", bold=True)

if __name__ == "__main__":
    cli()
