#!/bin/bash
# Export complete database snapshot as seed file for testing
# Captures entire mathematricks_trading database state for deterministic test restoration
# Run this after database is in desired clean state (e.g., after Phase 7 setup, before Phase 8 testing)

set -e

CONTAINER_NAME="mathematricks-trader-mongodb-1"
DATABASE="mathematricks_trading"
SEED_DIR="./seed_data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SEED_FILE="seed_${TIMESTAMP}.tar.gz"
TEMP_DIR="/tmp/mongodb_export_$$"

echo "============================================================"
echo "MongoDB Seed Data Export - Full Database Snapshot"
echo "============================================================"
echo "Container:  $CONTAINER_NAME"
echo "Database:   $DATABASE"
echo "Output:     $SEED_DIR/$SEED_FILE"
echo "Timestamp:  $TIMESTAMP"
echo ""

# Verify container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: Container $CONTAINER_NAME is not running"
    echo "   Start services with: make start"
    exit 1
fi

# Verify MongoDB is accessible
if ! docker exec "$CONTAINER_NAME" mongosh "$DATABASE" --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to MongoDB in container"
    echo "   Verify container is healthy: docker ps"
    exit 1
fi

# Create directories
mkdir -p "$SEED_DIR"
mkdir -p "$TEMP_DIR"

# Use a predictable path in the container for the dump
CONTAINER_DUMP_PATH="/tmp/mongo_dump_$$"

# Export database using mongodump
echo "📤 Exporting entire database..."
echo ""

docker exec "$CONTAINER_NAME" mongodump \
    --db "$DATABASE" \
    --out "$CONTAINER_DUMP_PATH/dump"

if [ $? -ne 0 ]; then
    echo "❌ Error: mongodump failed"
    docker exec "$CONTAINER_NAME" rm -rf "$CONTAINER_DUMP_PATH"
    exit 1
fi

# Copy dump from container to host
echo "📋 Copying dump from container to host..."
docker cp "$CONTAINER_NAME:$CONTAINER_DUMP_PATH/dump" "$TEMP_DIR/"

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to copy dump from container"
    docker exec "$CONTAINER_NAME" rm -rf "$CONTAINER_DUMP_PATH"
    exit 1
fi

# Clean up inside container
docker exec "$CONTAINER_NAME" rm -rf "$CONTAINER_DUMP_PATH"

# Verify dump directory was created and has content
if [ ! -d "$TEMP_DIR/dump/$DATABASE" ]; then
    echo "❌ Error: dump directory not found at $TEMP_DIR/dump/$DATABASE"
    echo "   Contents of $TEMP_DIR/dump/:"
    ls -la "$TEMP_DIR/dump/" || echo "   (empty)"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Count exported collections by BSON files
COLLECTION_COUNT=$(find "$TEMP_DIR/dump/$DATABASE" -type f -name "*.bson" 2>/dev/null | wc -l)
echo "✅ Exported $COLLECTION_COUNT collections"
echo ""

# Create compressed archive (exclude macOS metadata)
echo "🗜️  Creating compressed archive..."
export COPYFILE_DISABLE=1

cd "$TEMP_DIR" || exit 1
tar -czf "$SEED_FILE" dump/ 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ Error: tar compression failed"
    cd "$OLDPWD"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Move to seed directory
mv "$SEED_FILE" "$OLDPWD/$SEED_DIR/"
cd "$OLDPWD" || exit 1

# Store the seed path for validation
SEED_PATH="$SEED_DIR/$SEED_FILE"

# Verify archive was created before cleanup
if [ ! -f "$SEED_PATH" ]; then
    echo "❌ Error: Seed file was not created at $SEED_PATH"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "🔍 Validating export integrity..."
echo ""

# Extract archive to verify contents
VERIFY_TEMP_DIR="/tmp/verify_export_$$"
mkdir -p "$VERIFY_TEMP_DIR"
cd "$VERIFY_TEMP_DIR" || exit 1

tar -xzf "$OLDPWD/$SEED_PATH" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ VALIDATION FAILED: Cannot extract seed archive"
    cd "$OLDPWD"
    rm -rf "$TEMP_DIR" "$VERIFY_TEMP_DIR" "$SEED_PATH"
    exit 1
fi

# Get live database collections and counts
echo "  📊 Comparing collections and document counts..."
LIVE_COLLECTIONS=$(docker exec "$CONTAINER_NAME" mongosh "$DATABASE" --quiet --eval "
db.getCollectionNames().sort().forEach(function(col) { 
  print(col + ':' + db.getCollection(col).countDocuments({})); 
});" 2>/dev/null | sort)

# Copy extracted dump to container for verification
docker cp "$VERIFY_TEMP_DIR/dump/$DATABASE" "$CONTAINER_NAME:/tmp/verify_dump_$$" > /dev/null 2>&1

# Get exported collections and counts by restoring to a temp database
VERIFY_DB="temp_verify_$$"
docker exec "$CONTAINER_NAME" mongorestore \
    --db "$VERIFY_DB" \
    --dir "/tmp/verify_dump_$$" \
    --quiet > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "❌ VALIDATION FAILED: Cannot restore seed data for verification"
    docker exec "$CONTAINER_NAME" rm -rf "/tmp/verify_dump_$$"
    docker exec "$CONTAINER_NAME" mongosh "$VERIFY_DB" --quiet --eval "db.dropDatabase()" > /dev/null 2>&1
    cd "$OLDPWD"
    rm -rf "$TEMP_DIR" "$VERIFY_TEMP_DIR" "$SEED_PATH"
    exit 1
fi

EXPORTED_COLLECTIONS=$(docker exec "$CONTAINER_NAME" mongosh "$VERIFY_DB" --quiet --eval "
db.getCollectionNames().sort().forEach(function(col) { 
  print(col + ':' + db.getCollection(col).countDocuments({})); 
});" 2>/dev/null | sort)

# Clean up verification database and temp files
docker exec "$CONTAINER_NAME" mongosh "$VERIFY_DB" --quiet --eval "db.dropDatabase()" > /dev/null 2>&1
docker exec "$CONTAINER_NAME" rm -rf "/tmp/verify_dump_$$"
cd "$OLDPWD"
rm -rf "$VERIFY_TEMP_DIR"

# Compare collections
if [ "$LIVE_COLLECTIONS" != "$EXPORTED_COLLECTIONS" ]; then
    echo "❌ VALIDATION FAILED: Mismatch between live DB and exported seed data"
    echo ""
    echo "  Live Database Collections:"
    echo "$LIVE_COLLECTIONS" | sed 's/^/    /'
    echo ""
    echo "  Exported Seed Collections:"
    echo "$EXPORTED_COLLECTIONS" | sed 's/^/    /'
    echo ""
    echo "  Deleting invalid seed file: $SEED_PATH"
    rm -f "$SEED_PATH"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "  ✅ All collections match!"
echo "  ✅ All document counts match!"
echo ""

# Cleanup temp directory
rm -rf "$TEMP_DIR"

SEED_SIZE=$(du -h "$SEED_PATH" | cut -f1)

# Success summary
echo ""
echo "============================================================"
echo "✅ SEED DATA EXPORT COMPLETE"
echo "============================================================"
echo "Seed File:  $SEED_PATH"
echo "File Size:  $SEED_SIZE"
echo "Created:    $(date)"
echo ""

# Show recent seed files
echo "📦 Recent Backups:"
ls -lh "$SEED_DIR"/seed_*.tar.gz 2>/dev/null | tail -5 | awk '{printf "   %s  %s\n", $5, $9}' || echo "   (none)"
echo ""

# Next steps
echo "📋 Next Steps:"
echo "   1. Commit to git:"
echo "      git add $SEED_PATH"
echo "      git commit -m \"Add seed snapshot $TIMESTAMP\""
echo ""
echo "   2. Test restoration:"
echo "      bash scripts/restore_seed_data.sh"
echo ""
echo "   3. Before each test run:"
echo "      bash scripts/restore_seed_data.sh"
echo "      cd tests/signals_testing && python run_full_test.py --folder sample_signals"
echo ""
