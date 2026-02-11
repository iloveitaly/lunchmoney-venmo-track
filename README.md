# Lunch Money Venmo Track (Venmo Auto Cashout)

This is a small tool for automatically cashing out your Venmo balance such that each individual payment you receive will have an associated bank-transfer generated.

```
$ lunchmoney-venmo-track --token=XXX --allow-remaining
Your balance is $50
There are 3 transactions to cash-out

 -> Income: +$15.00 -- Mako (Dia beacon museum tickets)
 -> Income: +$15.00 -- David (Dia beacon museum tickets)
 -> Income: +$20.00 -- Randolf (Dinner)

All money transferred out!
```

This can be used as a cron script to automatically cash out your Venmo for you.

### Consistent tracking

By default the tool will only cashout amounts that add up to the most recent transactions. This is useful when the script is running on a cron-job and you want to be sure it never misses an individual payment cash out (This can happen when the tool runs immediately after a payment is received, but before the payment appears in the transaction list)

If you wish to cash-out everything use the `--allow-remaining` option. Otherwise the tool will exit when there is a remainder.

```
$ lunchmoney-venmo-track --token=XXX --allow-remaining
Your balance is $39.95
There are 3 transactions to cash-out

 -> Income: +$15.00 -- Mako (Dia beacon museum tickets)
 -> Income: $24.95 of extra balance

All money transferred out!
```

### Lunch Money Integration

In addition to automatic-cashout, this script can also integrate with [Lunch Money](https://lunchmoney.app/).

The script will look for transactions in Lunch Money which are part of an arbitrary Venmo category; these transactions will be matched against previously tracked Venmo transactions by matching the exact amount.

The Lunch Money transaction will then be updated with the Payee and Note from the Venmo transaction.

You will need to specify additional flags when running the script to do this.

```
$ lunchmoney-venmo-track --token=XXX --lunchmoney-token=XXX --lunchmoney-category=z-venmo
Your balance is $0.00
Running venmo_auto_cashout at 2026-02-10 10:00:00.000000
There are 0 income transactions to cash-out
There are 1 expense transactions to track

 -> Expense: -$28.29 -- Randolf Tjandra (Volcano curry)

Lunch Money Updates: 1 / 1 transactions matched

 -> Randolf Tjandra (Volcano curry) → LM: 242330937

All money transferred out!
```

My main use for this is to be able to better balance my bank account by associating Venmo transactions back to other charges in Lunch Money. Typically an incoming Venmo is a reimbursement for some other transaction that I covered for friends. I split and then group the transaction that was to cover my friends such that my categories reflect my "true spend" (e.g., I don't have a bunch of $100+ restaurants transactions).

### Getting your API token

You can use `uv run python` to retrieve your token:

> [!IMPORTANT]
> You may disregard the `device-id`, we only need the token.

```
$ uv run python
>>> from venmo_api import Client
>>> Client.get_access_token(username='myemail@gmail.com', password='myPassword')

IMPORTANT: Take a note of your device-id to avoid 2-factor-authentication for your next login.
device-id: xxxx
IMPORTANT: Your Access Token will NEVER expire, unless you logout manually (client.log_out(token)).
Take a note of your token, so you don't have to login every time.

Successfully logged in. Note your token and device-id
access_token: xxxx
device-id: xxxx
```

### Installation

This project uses `uv` for dependency management.

```bash
git clone https://github.com/iloveitaly/lunchmoney-venmo-track
cd lunchmoney-venmo-track
uv sync
```

### Environment Variables

You can set the following ENV variables instead of passing them as flags:

```bash
export VENMO_API_TOKEN=
export TRANSACTION_DB=
export LUNCHMONEY_TOKEN=
export LUNCHMONEY_CATEGORY=
export ALLOW_REMAINING=true
```
