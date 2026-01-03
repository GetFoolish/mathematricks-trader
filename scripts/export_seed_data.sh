#!/bin/bash
# Export current MongoDB data as timestamped tar.gz seed file
# Run this after applying fixes to create versioned seed data

set -e

CONTAINER_NAME="mathematricks-trader-mongodb-1"
DATABASE="mathematricks_trading"
SEED_DIR="./seed_data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SEED_FILE="seed_${TIMESTAMP}.tar.gz"
TEMP_DIR="/tmp/mongodb_export_$$"

echo "============================================================"
echo "MongoDB Seed Data Export"
echo "============================================================"
echo "Container: $CONTAINER_NAME"
echo "Database: $DATABASE"
echo "Output: $SEED_DIR/$SEED_FILE"
echo ""

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: Container $CONTAINER_NAME is not running"
    echo "   Run 'make start' first"
    exit 1
fi

# Create seed directory if it doesn't exist
mkdir -p "$SEED_DIR"

# Create temp directory
mkdir -p "$TEMP_DIR"

# Export current database to container
echo "📤 Exporting database from MongoDB..."
docker exec "$CONTAINER_NAME" mongodump \
    --db "$DATABASE" \
    --out /seed_data_export

# Copy from container to temp directory
echo "📥 Copying to temp directory..."
docker cp "$CONTAINER_NAME:/seed_data_export/$DATABASE" "$TEMP_DIR/"

# Clean up container export
docker exec "$CONTAINER_NAME" rm -rf /seed_data_export

# Create compressed archive (exclude macOS metadata files)
echo "🗜️  Creating compressed archive..."
cd "$TEMP_DIR"

# Set COPYFILE_DISABLE to prevent macOS metadata files in tar
export COPYFILE_DISABLE=1

tar -czf "$SEED_FILE" "$DATABASE"
mv "$SEED_FILE" "$OLDPWD/$SEED_DIR/"
cd "$OLDPWD"

# Clean up temp directory
rm -rf "$TEMP_DIR"

# List recent seed files
echo ""
echo "============================================================"
echo "✅ SEED DATA EXPORT COMPLETE"
echo "============================================================"
echo "Seed file: $SEED_DIR/$SEED_FILE"
echo ""
echo "📦 Recent seed files:"
ls -lht "$SEED_DIR"/seed_*.tar.gz 2>/dev/null | head -5 || echo "   (none)"
echo ""
echo "📋 Next steps:"
echo "1. Review: tar -tzf $SEED_DIR/$SEED_FILE | head -20"
echo "2. Commit: git add $SEED_DIR/$SEED_FILE && git commit -m 'Add seed data $TIMESTAMP'"
echo "3. Test: make clean && make start"
echo ""
echo "💡 Old seed files can be deleted manually if needed"
echo ""
