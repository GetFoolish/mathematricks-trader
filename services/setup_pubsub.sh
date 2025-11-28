#!/bin/bash
# Setup Google Cloud Pub/Sub Topics and Subscriptions for MVP

PROJECT_ID=${GCP_PROJECT_ID:-"mathematricks-trader"}

echo "Setting up Pub/Sub for project: $PROJECT_ID"

# Create Topics
echo "Creating Pub/Sub topics..."
gcloud pubsub topics create raw-signals --project=$PROJECT_ID
gcloud pubsub topics create standardized-signals --project=$PROJECT_ID
gcloud pubsub topics create trading-orders --project=$PROJECT_ID
gcloud pubsub topics create execution-confirmations --project=$PROJECT_ID
gcloud pubsub topics create account-updates --project=$PROJECT_ID

# Create Subscriptions
echo "Creating Pub/Sub subscriptions..."

# CerebroService subscribes to standardized-signals
gcloud pubsub subscriptions create standardized-signals-sub \
    --topic=standardized-signals \
    --project=$PROJECT_ID \
    --ack-deadline=60

# ExecutionService subscribes to trading-orders
gcloud pubsub subscriptions create trading-orders-sub \
    --topic=trading-orders \
    --project=$PROJECT_ID \
    --ack-deadline=60

# AccountDataService subscribes to execution-confirmations
gcloud pubsub subscriptions create execution-confirmations-sub \
    --topic=execution-confirmations \
    --project=$PROJECT_ID \
    --ack-deadline=30

# AccountDataService subscribes to account-updates
gcloud pubsub subscriptions create account-updates-sub \
    --topic=account-updates \
    --project=$PROJECT_ID \
    --ack-deadline=30

echo "Pub/Sub setup complete!"
echo "Topics: raw-signals, standardized-signals, trading-orders, execution-confirmations, account-updates"
echo "Subscriptions: standardized-signals-sub, trading-orders-sub, execution-confirmations-sub, account-updates-sub"
