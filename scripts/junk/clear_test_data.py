#!/usr/bin/env python3
"""
Clear test data from MongoDB collections.

Clears:
- trading_signals_raw
- signal_store
- trading_orders

Usage:
    python scripts/junk/clear_test_data.py
"""
import os
import subprocess
import sys
import time
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def clear_test_data():
    """Clear test collections from MongoDB"""
    # Use MONGODB_URI_LOCAL for Mac scripts, fallback to MONGODB_URI for Docker
    mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI')

    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)

    db = client['mathematricks_trading']

    collections = ['trading_signals_raw', 'signal_store', 'trading_orders']

    print("=" * 60)
    print("Clearing test data...")
    print("=" * 60)

    for coll_name in collections:
        before_count = db[coll_name].count_documents({})
        result = db[coll_name].delete_many({})
        print(f"  {coll_name}: deleted {result.deleted_count} documents (was {before_count})")

    # Restart execution-service to clear in-memory duplicate tracking
    print("\nRestarting execution-service to clear in-memory state...")
    try:
        subprocess.run(
            ["docker", "restart", "mathematricks-trader-execution-service-1"],
            check=True,
            capture_output=True
        )
        time.sleep(3)  # Wait for service to restart
        print("  execution-service restarted")
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not restart execution-service: {e}")
    except FileNotFoundError:
        print("  Warning: docker command not found, skipping container restart")

    print("=" * 60)
    print("Done!")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    clear_test_data()
