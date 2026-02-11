#!/bin/sh
set -e

# Default to 6am if SCHEDULE is not set
SCHEDULE="${SCHEDULE:-0 6 * * *}"

echo "setting up cron job with schedule: $SCHEDULE"
echo "$SCHEDULE lunchmoney-venmo-track" > Cronfile

# Run tasker with the generated Cronfile
exec tasker -file Cronfile
