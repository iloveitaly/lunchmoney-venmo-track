import sys

import click
from click_default_group import DefaultGroup
from decouple import config
from structlog_config import configure_logger
from venmo_api import Client

from lunchmoney_venmo_track.heartbeat import send_heartbeat
from lunchmoney_venmo_track.internet import wait_for_internet_connection
from lunchmoney_venmo_track.venmo import process_venmo_transactions


def setup_logging():
    # Read environment variables directly to determine configuration
    json_logging = config("JSON_LOGGING", default=True, cast=bool)

    # Configure the logger using structlog-config
    configure_logger(json_logger=json_logging)


class DefaultCommandGroup(DefaultGroup):
    def format_options(self, ctx, formatter):
        default_cmd = self.get_command(ctx, self.default_cmd_name)
        if default_cmd:
            default_cmd.format_options(ctx, formatter)

        self.format_commands(ctx, formatter)


@click.group(cls=DefaultCommandGroup, default="sync", default_if_no_args=True)
def cli():
    """
    Automatically cash-out your Venmo balance as individual transfers
    """


@cli.command("sync")
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Do not actually initiate bank transfers",
)
@click.option(
    "--skip-transfer/--no-skip-transfer",
    default=False,
    help="Skip bank transfers but still update the DB and Lunch Money",
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
def sync(
    dry_run: bool,
    skip_transfer: bool,
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

    # If we are running in a cron/non-interactive context, wait for internet
    if not sys.stdin.isatty():
        wait_for_internet_connection()

    if lunchmoney_token and not transaction_db:
        raise click.UsageError(
            "--transaction-db must be specified to use the LM integration"
        )

    if (lunchmoney_token is None) != (lunchmoney_category is None):
        raise click.UsageError(
            "--lunchmoney-token and --lunchmoney-category are both required for LM integration"
        )

    process_venmo_transactions(
        token=token,
        db_path=transaction_db,
        lunchmoney_token=lunchmoney_token,
        lunchmoney_category=lunchmoney_category,
        dry_run=dry_run,
        skip_transfer=skip_transfer,
        allow_remaining=allow_remaining,
    )

    click.secho(
        "\nAll Venmo transactions processed successfully!", fg="green", bold=True
    )

    heartbeat_url = config("HEARTBEAT_URL", default=None)
    if heartbeat_url:
        send_heartbeat(heartbeat_url)


@cli.command("get-access-token")
@click.option(
    "--username",
    prompt=True,
    help="Venmo username, email, or phone number",
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    help="Venmo password",
)
@click.option(
    "--device-id",
    default=None,
    help="Optional device ID to avoid two-factor authentication",
)
def get_access_token(
    username: str,
    password: str,
    device_id: str | None,
):
    """
    Retrieve Venmo API access token using credentials
    """
    token = Client.get_access_token(
        username=username,
        password=password,
        device_id=device_id,
    )

    if token:
        click.secho(f"\nYour Venmo API token: {token}", fg="green", bold=True)


if __name__ == "__main__":
    cli()
