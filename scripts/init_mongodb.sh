#!/bin/bash
# Initialize MongoDB with seed data on first startup only.
# Uses the latest timestamped seed_*.tar.gz file from /seed_data
# Skips if database already has data (to avoid overwriting developer work).

set -e

MONGODB_URI="mongodb://mongodb:27017"
DATABASE="mathematricks_trading"
SEED_DIR="/seed_data"
TEMP_DIR="/tmp/mongodb_seed_$$"

echo "Checking if database needs seeding..."

# Check if database has any collections
COLLECTIONS=$(mongosh "$MONGODB_URI/$DATABASE" --quiet --eval 'db.getCollectionNames().length')

if [ "$COLLECTIONS" -gt 0 ]; then
    echo "✓ Database already has $COLLECTIONS collections. Skipping seed."
    exit 0
fi

# Find latest seed file
LATEST_SEED=$(ls -t "$SEED_DIR"/seed_*.tar.gz 2>/dev/null | head -1)

if [ -z "$LATEST_SEED" ]; then
    echo "⚠️  No seed files found at $SEED_DIR/seed_*.tar.gz"
    echo "   Create seed data with: make export-seed-data"
    exit 0
fi

echo "📦 Database is empty. Restoring from seed..."
echo "   Using: $(basename $LATEST_SEED)"

# Create temp directory and extract seed
mkdir -p "$TEMP_DIR"
tar -xzf "$LATEST_SEED" -C "$TEMP_DIR"

# Remove macOS metadata files if they exist
find "$TEMP_DIR" -name "._*" -delete
find "$TEMP_DIR" -name ".DS_Store" -delete

# Restore from extracted data
mongorestore --uri "$MONGODB_URI" "$TEMP_DIR"

# Clean up
rm -rf "$TEMP_DIR"

echo "✅ Seed data restored successfully!"
