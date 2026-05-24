# Sync Venmo Balance and Transactions to Lunch Money

This is a small tool for automatically cashing out your Venmo balance so that each individual payment you receive has an associated bank transfer. It also syncs Venmo transaction notes and payees back to Lunch Money.

I built this because I wanted a cleaner way to track Venmo reimbursements. Typically, an incoming Venmo is for a shared expense I've already covered. By syncing the Venmo metadata back to Lunch Money, I can accurately categorize my "true spend" without a mess of unlinked transactions.

### Installation

This project uses `uv` for dependency management.

```bash
git clone https://github.com/iloveitaly/lunchmoney-venmo-track
cd lunchmoney-venmo-track
uv sync
```

### Usage

```bash
$ lunchmoney-venmo-track --token=XXX --allow-remaining
Your balance is $50
There are 3 transactions to cash-out

 -> Income: +$15.00 -- Mako (Dia beacon museum tickets)
 -> Income: +$15.00 -- David (Dia beacon museum tickets)
 -> Income: +$20.00 -- Randolf (Dinner)

All Venmo transactions processed successfully!
```

### Features

* **Automatic Cashout**: Triggers bank transfers for your Venmo balance based on individual received payments.
* **Lunch Money Sync**: Matches Venmo transactions to Lunch Money entries by amount and updates them with notes and payee names.
* **Consistent Tracking**: Only cashes out amounts that match recent transactions to ensure everything is accounted for.
* **Cron Ready**: Includes built-in support for healthcheck heartbeats and internet connection retries for reliable scheduled execution.
* **Structured Logging**: Uses `structlog` for clean, searchable logs in both console and JSON formats.

### Consistent Tracking

By default, the tool only cashes out amounts that add up to the most recent transactions. This is useful when the script is running on a cron-job and you want to be sure it never misses an individual payment cash out (This can happen when the tool runs immediately after a payment is received, but before the payment appears in the transaction list).

If you wish to cash-out everything, use the `--allow-remaining` option. Otherwise, the tool will exit when there is a remainder.

```bash
$ lunchmoney-venmo-track --token=XXX --allow-remaining
Your balance is $39.95
There are 3 transactions to cash-out

 -> Income: +$15.00 -- Mako (Dia beacon museum tickets)
 -> Income: $24.95 of extra balance

All Venmo transactions processed successfully!
```

### Lunch Money Integration

The script looks for transactions in Lunch Money which are part of an arbitrary Venmo category; these transactions are matched against previously tracked Venmo transactions by matching the exact amount.

The Lunch Money transaction is then updated with the Payee and Note from the Venmo transaction.

```bash
$ lunchmoney-venmo-track --token=XXX --lunchmoney-token=XXX --lunchmoney-category=z-venmo
Your balance is $0.00
There are 0 income transactions to cash-out
There are 1 expense transactions to track

 -> Expense: -$28.29 -- Randolf Tjandra (Volcano curry)

Lunch Money Updates: 1 / 1 transactions matched

 -> Randolf Tjandra (Volcano curry) → LM: 242330937

All Venmo transactions processed successfully!
```

### Getting your API token

You can use `uv run python` to retrieve your token:

> [!IMPORTANT]
> You may disregard the `device-id`, we only need the token.

```python
from venmo_api import Client
Client.get_access_token(username='myemail@gmail.com', password='myPassword')
```

### Heartbeat Support

You can specify a `HEARTBEAT_URL` environment variable to be pinged after each successful execution. This is highly recommended for monitoring your cron jobs. We recommend using [Uptime Kuma](https://github.com/louislam/uptime-kuma) to monitor these heartbeats.

### Environment Variables

You can set the following variables instead of passing flags:

```bash
export VENMO_API_TOKEN=
export TRANSACTION_DB=
export LUNCHMONEY_TOKEN=
export LUNCHMONEY_CATEGORY=
export ALLOW_REMAINING=true
export HEARTBEAT_URL=
```

## [MIT License](LICENSE.md)
