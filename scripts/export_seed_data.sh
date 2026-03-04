#!/bin/bash
# Export complete database snapshot as seed file for testing
# Captures entire mathematricks_trading database state for deterministic test restoration
# Run this after database is in desired clean state (e.g., after Phase 7 setup, before Phase 8 testing)
#
# Usage:
#   ./export_seed_data.sh           # Export from local MongoDB (default)
#   ./export_seed_data.sh local     # Export from local MongoDB
#   ./export_seed_data.sh cloud     # Export from cloud MongoDB (Atlas)

set -e

# Deployment target (local or cloud)
DEPLOY="${1:-local}"

CONTAINER_NAME="mathematricks-trader-mongodb-1"
DATABASE="mathematricks_trading"
SEED_DIR="./seed_data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SEED_FILE="seed_${TIMESTAMP}_${DEPLOY}.tar.gz"
TEMP_DIR="/tmp/mongodb_export_$$"

# Load environment variables for cloud connection
if [ "$DEPLOY" = "cloud" ]; then
    if [ -f .env ]; then
        export $(grep -v '^#' .env | grep MONGODB_URI_CLOUD | xargs)
    fi
    
    if [ -z "$MONGODB_URI_CLOUD" ]; then
        echo "❌ Error: MONGODB_URI_CLOUD not set in .env file"
        exit 1
    fi
    
    MONGODB_URI="$MONGODB_URI_CLOUD"
    MONGO_LABEL="☁️  Cloud MongoDB (Atlas)"
else
    MONGODB_URI="mongodb://localhost:27018"
    MONGO_LABEL="🏠 Local MongoDB (Docker)"
fi

echo "============================================================"
echo "MongoDB Seed Data Export - Full Database Snapshot"
echo "============================================================"
echo "Source:     $MONGO_LABEL"
echo "Database:   $DATABASE"
echo "Output:     $SEED_DIR/$SEED_FILE"
echo "Timestamp:  $TIMESTAMP"
echo ""

# Verify prerequisites based on deployment target
if [ "$DEPLOY" = "local" ]; then
    # Verify container is running
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        echo "❌ Error: Container $CONTAINER_NAME is not running"
        echo "   Start services with: make start"
        exit 1
    fi

    # Verify MongoDB is accessible
    if ! docker exec "$CONTAINER_NAME" mongosh --port 27018 "$DATABASE" --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo "❌ Error: Cannot connect to MongoDB in container"
        echo "   Verify container is healthy: docker ps"
        exit 1
    fi
else
    # Cloud: Check if mongodump is installed
    if ! command -v mongodump &> /dev/null; then
        echo "❌ Error: mongodump not found in PATH"
        echo "   Install MongoDB Database Tools: https://www.mongodb.com/try/download/database-tools"
        echo "   macOS: brew install mongodb/brew/mongodb-database-tools"
        exit 1
    fi
    
    # Verify cloud MongoDB is accessible
    if ! mongosh "$MONGODB_URI" --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo "❌ Error: Cannot connect to cloud MongoDB"
        echo "   Verify MONGODB_URI_CLOUD in .env file"
        exit 1
    fi
fi

# Create directories
mkdir -p "$SEED_DIR"
mkdir -p "$TEMP_DIR"

# Export database using mongodump
echo "📤 Exporting entire database..."
echo ""

if [ "$DEPLOY" = "local" ]; then
    # Use a predictable path in the container for the dump
    CONTAINER_DUMP_PATH="/tmp/mongo_dump_$$"

    docker exec "$CONTAINER_NAME" mongodump \
        --port 27018 \
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
else
    # Cloud: Use mongodump directly
    mongodump \
        --uri="$MONGODB_URI" \
        --db="$DATABASE" \
        --out="$TEMP_DIR/dump"

    if [ $? -ne 0 ]; then
        echo "❌ Error: mongodump failed"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
fi

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

if [ "$DEPLOY" = "local" ]; then
    LIVE_COLLECTIONS=$(docker exec "$CONTAINER_NAME" mongosh --port 27018 "$DATABASE" --quiet --eval "
    db.getCollectionNames().sort().forEach(function(col) { 
      print(col + ':' + db.getCollection(col).countDocuments({})); 
    });" 2>/dev/null | sort)

    # Copy extracted dump to container for verification
    docker cp "$VERIFY_TEMP_DIR/dump/$DATABASE" "$CONTAINER_NAME:/tmp/verify_dump_$$" > /dev/null 2>&1

    # Get exported collections and counts by restoring to a temp database
    VERIFY_DB="temp_verify_$$"
    docker exec "$CONTAINER_NAME" mongorestore \
        --port 27018 \
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

    EXPORTED_COLLECTIONS=$(docker exec "$CONTAINER_NAME" mongosh --port 27018 "$VERIFY_DB" --quiet --eval "
    db.getCollectionNames().sort().forEach(function(col) { 
      print(col + ':' + db.getCollection(col).countDocuments({})); 
    });" 2>/dev/null | sort)

    # Clean up verification database and temp files
    docker exec "$CONTAINER_NAME" mongosh --port 27018 "$VERIFY_DB" --quiet --eval "db.dropDatabase()" > /dev/null 2>&1
    docker exec "$CONTAINER_NAME" rm -rf "/tmp/verify_dump_$$"
else
    # Cloud: Use mongosh directly (without --quiet for proper output)
    # Note: Cloud URI format requires database name without extra slash
    CLOUD_URI_BASE="${MONGODB_URI%/}"  # Remove trailing slash if present
    LIVE_COLLECTIONS=$(mongosh "${CLOUD_URI_BASE}/${DATABASE}" --eval "
    db.getCollectionNames().sort().forEach(function(col) { 
      print(col + ':' + db.getCollection(col).countDocuments({})); 
    });" 2>/dev/null | grep -E "^[a-z_]+:[0-9]+$" | sort)

    # Get exported collections and counts by restoring to a temp database
    VERIFY_DB="temp_verify_$$"
    mongorestore \
        --uri="$MONGODB_URI" \
        --db="$VERIFY_DB" \
        --dir="$VERIFY_TEMP_DIR/dump/$DATABASE" \
        --quiet > /dev/null 2>&1

    if [ $? -ne 0 ]; then
        echo "❌ VALIDATION FAILED: Cannot restore seed data for verification"
        mongosh "${CLOUD_URI_BASE}/${VERIFY_DB}" --quiet --eval "db.dropDatabase()" > /dev/null 2>&1
        cd "$OLDPWD"
        rm -rf "$TEMP_DIR" "$VERIFY_TEMP_DIR" "$SEED_PATH"
        exit 1
    fi

    EXPORTED_COLLECTIONS=$(mongosh "${CLOUD_URI_BASE}/${VERIFY_DB}" --eval "
    db.getCollectionNames().sort().forEach(function(col) { 
      print(col + ':' + db.getCollection(col).countDocuments({})); 
    });" 2>/dev/null | grep -E "^[a-z_]+:[0-9]+$" | sort)

    # Clean up verification database
    mongosh "${CLOUD_URI_BASE}/${VERIFY_DB}" --quiet --eval "db.dropDatabase()" > /dev/null 2>&1
fi
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
echo "Source:     $MONGO_LABEL"
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
echo "      git commit -m \"Add seed snapshot $TIMESTAMP from $DEPLOY\""
echo ""
echo "   2. Test restoration:"
echo "      bash scripts/restore_seed_data.sh"
echo ""
echo "   3. Before each test run:"
echo "      bash scripts/restore_seed_data.sh"
echo "      cd tests/signals_testing && python run_full_test.py --folder sample_signals"
echo ""
