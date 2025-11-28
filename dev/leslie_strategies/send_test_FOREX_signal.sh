#!/bin/bash

# Script to delete existing signal and send fresh LeslieForex signal
# This allows repeated testing without duplicate signals

set -e  # Exit on error

echo "======================================"
echo "LeslieForex Test Signal Sender"
echo "======================================"
echo ""

# MongoDB connection string (correct database: mathematricks_signals)
MONGO_URI="mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_signals"

# Python path
PYTHON_PATH="/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks-trader/venv/bin/python"

# Signal details
STRATEGY_NAME="Forex"
TICKER="AUDNZD"
ACTION="SELL"
PRICE=0
QUANTITY=2
PASSPHRASE="yahoo123"
API_ENDPOINT="https://staging.mathematricks.fund/api/signals"

# Generate current EPOCH timestamp
CURRENT_EPOCH=$(date +%s)
SIGNAL_ID="signal_${CURRENT_EPOCH}$(date +%3N)"

echo "Step 1: Deleting existing signals for $STRATEGY_NAME - $TICKER..."
echo ""

# Delete existing signals matching strategy_name and ticker using Python
DELETE_RESULT=$($PYTHON_PATH -c "
from pymongo import MongoClient

uri = '$MONGO_URI'
client = MongoClient(uri)
db = client['mathematricks_signals']

result = db.trading_signals.delete_many({
    'strategy_name': '$STRATEGY_NAME',
    'signal.ticker': '$TICKER'
})

print(f'Deleted {result.deleted_count} signals')
" 2>&1)

echo "$DELETE_RESULT"

echo ""
echo "Step 2: Sending fresh signal..."
echo "  Strategy: $STRATEGY_NAME"
echo "  Ticker: $TICKER"
echo "  Action: $ACTION"
echo "  Quantity: $QUANTITY"
echo "  Signal ID: $SIGNAL_ID"
echo "  Timestamp: $CURRENT_EPOCH"
echo ""

# Send the signal via curl
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "{
    \"strategy_name\": \"$STRATEGY_NAME\",
    \"signal_sent_EPOCH\": $CURRENT_EPOCH,
    \"signalID\": \"$SIGNAL_ID\",
    \"passphrase\": \"$PASSPHRASE\",
    \"signal\": {
      \"ticker\": \"$TICKER\",
      \"action\": \"$ACTION\",
      \"price\": $PRICE,
      \"quantity\": $QUANTITY
    }
  }")

# Extract HTTP status code
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')

echo "Response:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 201 ]; then
  echo "✅ Signal sent successfully! (HTTP $HTTP_STATUS)"
else
  echo "❌ Signal failed with HTTP status: $HTTP_STATUS"
  exit 1
fi

echo ""
echo "======================================"
echo "Done!"
echo "======================================"
