#!/bin/bash
# Restore MongoDB from a seed data file

set -e

CONTAINER_NAME="mathematricks-trader-mongodb-1"
SEED_DIR="./seed_data"
TEMP_DIR="/tmp/mongodb_restore_$$"

echo "============================================================"
echo "MongoDB Seed Data Restore"
echo "============================================================"
echo ""

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: Container $CONTAINER_NAME is not running"
    echo "   Run 'make start' first"
    exit 1
fi

# Find latest seed file
LATEST_SEED=$(ls -t "$SEED_DIR"/seed_*.tar.gz 2>/dev/null | head -1)

if [ -z "$LATEST_SEED" ]; then
    echo "❌ Error: No seed files found at $SEED_DIR/seed_*.tar.gz"
    exit 1
fi

echo "📦 Restoring from seed file..."
echo "   Using: $(basename $LATEST_SEED)"
echo ""

# Create temp directory
mkdir -p "$TEMP_DIR"

# Extract seed file
echo "📥 Extracting seed file..."
tar -xzf "$LATEST_SEED" -C "$TEMP_DIR"

# Remove macOS metadata files if they exist
find "$TEMP_DIR" -name "._*" -delete 2>/dev/null || true
find "$TEMP_DIR" -name ".DS_Store" -delete 2>/dev/null || true

# Copy to MongoDB container
echo "📤 Copying to MongoDB container..."
docker cp "$TEMP_DIR/dump" "$CONTAINER_NAME:/seed_restore_data"

# Drop existing database to avoid duplicate key errors
echo "🗑️  Dropping existing database..."
docker exec "$CONTAINER_NAME" mongosh --port 27018 mathematricks_trading --quiet --eval "db.dropDatabase()"

# Restore using mongorestore with --drop flag to ensure clean replacement
echo "🔄 Running mongorestore..."
docker exec "$CONTAINER_NAME" mongorestore --port 27018 --drop /seed_restore_data

# Clean up
docker exec "$CONTAINER_NAME" rm -rf /seed_restore_data
rm -rf "$TEMP_DIR"

echo ""
echo "============================================================"
echo "✅ SEED DATA RESTORED SUCCESSFULLY"
echo "============================================================"
echo ""
