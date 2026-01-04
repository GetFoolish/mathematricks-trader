#!/bin/bash
# Export last 50 documents from each collection in mathematricks_trading as seed file
# Run this after applying fixes to create versioned seed data

set -e

CONTAINER_NAME="mathematricks-trader-mongodb-1"
DATABASE="mathematricks_trading"
SEED_DIR="./seed_data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SEED_FILE="seed_${TIMESTAMP}.tar.gz"
TEMP_DIR="/tmp/mongodb_export_$$"

echo "============================================================"
echo "MongoDB Seed Data Export (Last 50 docs per collection)"
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

# Get list of collections in the database
echo "📋 Fetching collection list..."
COLLECTIONS=$(docker exec "$CONTAINER_NAME" mongosh "$DATABASE" --quiet --eval "db.getCollectionNames().join('\n')")

if [ -z "$COLLECTIONS" ]; then
    echo "❌ Error: Could not fetch collections from $DATABASE"
    exit 1
fi

echo "📤 Exporting using mongodump (last 50 docs per collection)..."
echo ""

# Use mongodump with query to limit to last 50 documents per collection
for COLLECTION in $COLLECTIONS; do
    echo "  ↳ Dumping $COLLECTION..."
    # Get count of documents
    COUNT=$(docker exec "$CONTAINER_NAME" mongosh "$DATABASE" --quiet --eval "db.$COLLECTION.countDocuments()")
    
    # Calculate skip to get last 50 docs
    SKIP=$((COUNT > 50 ? COUNT - 50 : 0))
    
    # Use mongodump to dump with skip to get last 50 documents
    docker exec "$CONTAINER_NAME" mongodump \
        --db "$DATABASE" \
        --collection "$COLLECTION" \
        --out "$TEMP_DIR/dump" \
        --query "{}" \
        --skip "$SKIP" \
        --quiet
done

echo ""

# Create compressed archive (exclude macOS metadata files)
echo "🗜️  Creating compressed tar.gz archive..."

# Set COPYFILE_DISABLE to prevent macOS metadata files in tar
export COPYFILE_DISABLE=1

cd "$TEMP_DIR"
tar -czf "$SEED_FILE" dump/
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
