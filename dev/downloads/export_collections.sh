#!/bin/bash

# Export MongoDB Collections to JSON
# Exports key collections for sharing with collaborators

set -e

# Configuration
DB_NAME="mathematricks_trading"
OUTPUT_DIR="./dev/downloads/exported_collections"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Collections to export
COLLECTIONS=(
    "current_allocation"
    "portfolio_tests"
    "strategies"
    "trading_accounts"
)

echo "=========================================="
echo "MongoDB Collection Export Tool"
echo "=========================================="
echo ""
echo "Database: $DB_NAME"
echo "Output Directory: $OUTPUT_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Export each collection
for collection in "${COLLECTIONS[@]}"; do
    output_file="${OUTPUT_DIR}/${collection}_${TIMESTAMP}.json"

    echo "Exporting collection: $collection"

    mongoexport \
        --db="$DB_NAME" \
        --collection="$collection" \
        --out="$output_file" \
        --jsonArray \
        --pretty

    if [ $? -eq 0 ]; then
        # Get document count
        doc_count=$(mongosh --quiet "$DB_NAME" --eval "db.${collection}.countDocuments({})")
        file_size=$(du -h "$output_file" | cut -f1)

        echo "  ✅ Exported $doc_count documents ($file_size)"
    else
        echo "  ❌ Failed to export $collection"
    fi
    echo ""
done

echo "=========================================="
echo "Export Complete!"
echo "=========================================="
echo ""
echo "Exported files:"
ls -lh "$OUTPUT_DIR"/*_${TIMESTAMP}.json
echo ""
echo "To share these collections, zip them up:"
echo "  cd $OUTPUT_DIR"
echo "  zip -r collections_export_${TIMESTAMP}.zip *_${TIMESTAMP}.json"
echo ""
echo "To import on another system:"
echo "  mongoimport --db=mathematricks_trading --collection=<name> --file=<file>.json --jsonArray"
