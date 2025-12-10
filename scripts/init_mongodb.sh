#!/bin/bash
# Initialize MongoDB with seed data on first startup only.
# Skips if database already has data (to avoid overwriting developer work).

set -e

MONGODB_URI="mongodb://mongodb:27017"
DATABASE="mathematricks_trading"
DUMP_PATH="/seed_data/mongodb_dump"

echo "Checking if database needs seeding..."

# Check if database has any collections
COLLECTIONS=$(mongosh "$MONGODB_URI/$DATABASE" --quiet --eval 'db.getCollectionNames().length')

if [ "$COLLECTIONS" -gt 0 ]; then
    echo "✓ Database already has $COLLECTIONS collections. Skipping seed."
    exit 0
fi

# Check if dump directory exists and has data
if [ ! -d "$DUMP_PATH/$DATABASE" ]; then
    echo "⚠️  No seed data found at $DUMP_PATH/$DATABASE. Skipping."
    exit 0
fi

echo "📦 Database is empty. Restoring seed data..."
mongorestore --uri "$MONGODB_URI" "$DUMP_PATH"
echo "✅ Seed data restored successfully!"
