#!/bin/bash
# Setup Google Cloud Pub/Sub Emulator for Local Testing
# This creates all topics and subscriptions needed for MVP microservices

set -e

PROJECT_ID="mathematricks-trader"
EMULATOR_HOST="localhost:8085"

echo "=========================================="
echo "PUB/SUB EMULATOR SETUP"
echo "=========================================="
echo ""

# Check if emulator is running
if curl -s $EMULATOR_HOST > /dev/null 2>&1; then
    echo "✓ Pub/Sub emulator is running at $EMULATOR_HOST"
else
    echo "✗ Pub/Sub emulator not running"
    echo ""
    echo "Starting emulator..."
    gcloud beta emulators pubsub start --host-port=$EMULATOR_HOST &
    sleep 3
    echo "✓ Emulator started"
fi

# Export environment variable for clients
export PUBSUB_EMULATOR_HOST=$EMULATOR_HOST

# Create topics using gcloud
echo ""
echo "Creating Pub/Sub topics..."
gcloud pubsub topics create standardized-signals --project=$PROJECT_ID 2>/dev/null || echo "  standardized-signals already exists"
gcloud pubsub topics create trading-orders --project=$PROJECT_ID 2>/dev/null || echo "  trading-orders already exists"
gcloud pubsub topics create execution-confirmations --project=$PROJECT_ID 2>/dev/null || echo "  execution-confirmations already exists"
gcloud pubsub topics create account-updates --project=$PROJECT_ID 2>/dev/null || echo "  account-updates already exists"

echo ""
echo "Creating Pub/Sub subscriptions..."
gcloud pubsub subscriptions create standardized-signals-sub \
    --topic=standardized-signals \
    --project=$PROJECT_ID \
    --ack-deadline=60 2>/dev/null || echo "  standardized-signals-sub already exists"

gcloud pubsub subscriptions create trading-orders-sub \
    --topic=trading-orders \
    --project=$PROJECT_ID \
    --ack-deadline=60 2>/dev/null || echo "  trading-orders-sub already exists"

gcloud pubsub subscriptions create execution-confirmations-sub \
    --topic=execution-confirmations \
    --project=$PROJECT_ID \
    --ack-deadline=30 2>/dev/null || echo "  execution-confirmations-sub already exists"

gcloud pubsub subscriptions create account-updates-sub \
    --topic=account-updates \
    --project=$PROJECT_ID \
    --ack-deadline=30 2>/dev/null || echo "  account-updates-sub already exists"

echo ""
echo "=========================================="
echo "✓ Pub/Sub Emulator Setup Complete!"
echo "=========================================="
echo ""
echo "Topics: standardized-signals, trading-orders, execution-confirmations, account-updates"
echo "Subscriptions: all topics have matching subscriptions"
echo ""
echo "Environment variable:"
echo "export PUBSUB_EMULATOR_HOST=$EMULATOR_HOST"
echo ""
