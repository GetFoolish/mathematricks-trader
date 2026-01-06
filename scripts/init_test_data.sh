#!/bin/bash
# Initialize MongoDB with test data for signal testing

set -e

CONTAINER_NAME="mathematricks-trader-mongodb-1"
SCRIPT_PATH="./scripts/init_test_data.js"

echo "============================================================"
echo "MongoDB Test Data Initializer"
echo "============================================================"
echo ""

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: Container $CONTAINER_NAME is not running"
    echo "   Run 'make start' first"
    exit 1
fi

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Error: Script not found at $SCRIPT_PATH"
    exit 1
fi

# Run the MongoDB script
echo "📥 Running initialization script..."
echo ""
docker exec -i "$CONTAINER_NAME" mongosh mathematricks --quiet < "$SCRIPT_PATH"

echo ""
echo "============================================================"
echo "Next Step: Restart Cerebro Service"
echo "============================================================"
echo ""
echo "Run: docker-compose restart cerebro-service"
echo ""
