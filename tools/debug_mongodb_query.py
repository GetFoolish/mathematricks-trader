#!/usr/bin/env python3
"""
Debug MongoDB Query
Tests the exact query used by SignalIngestionService to see why signals aren't being detected
"""
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_mongodb_query(environment="staging"):
    """Test the exact query used by catch-up mode"""

    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        print("❌ MONGODB_URI not found in .env")
        return

    print(f"🔍 Testing MongoDB query for environment: {environment}")
    print(f"📡 Connecting to MongoDB...")

    try:
        # Connect to MongoDB (same as SignalIngestionService)
        client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=5000,
            tls=True,
            tlsAllowInvalidCertificates=True
        )

        # Test connection
        client.admin.command('ping')
        print(f"✅ Connected to MongoDB")

        # Get collection
        db = client['mathematricks_trading']
        collection = db['trading_signals']

        print(f"\n📊 Collection: mathematricks_trading.trading_signals")
        print(f"📊 Total documents: {collection.count_documents({})}")

        # Test the exact query used in catch-up mode
        query_filter = {
            'signal_processed': {'$ne': True},
            'environment': environment
        }

        print(f"\n🔍 Query filter (catch-up mode):")
        print(f"   {query_filter}")

        results = list(collection.find(query_filter).sort('received_at', 1))

        print(f"\n📥 Results: {len(results)} documents found")

        if results:
            print(f"\n" + "="*80)
            for i, doc in enumerate(results, 1):
                print(f"\nDocument {i}:")
                print(f"  _id: {doc.get('_id')}")
                print(f"  signalID: {doc.get('signalID')}")
                print(f"  strategy_name: {doc.get('strategy_name')}")
                print(f"  environment: {doc.get('environment')}")
                print(f"  signal_processed: {doc.get('signal_processed')} (type: {type(doc.get('signal_processed')).__name__})")
                print(f"  received_at: {doc.get('received_at')}")
                print(f"  signal: {doc.get('signal')}")
        else:
            print(f"\n⚠️  No documents matched the query")

            # Check if there are ANY staging signals
            staging_count = collection.count_documents({'environment': environment})
            print(f"\n📊 Total {environment} signals: {staging_count}")

            if staging_count > 0:
                # Show some staging signals to understand the data
                print(f"\n📋 Sample {environment} signals (showing signal_processed field):")
                for doc in collection.find({'environment': environment}).limit(5):
                    print(f"  - signalID: {doc.get('signalID')}, signal_processed: {doc.get('signal_processed')} (type: {type(doc.get('signal_processed')).__name__})")

        print(f"\n" + "="*80)

        # Close connection
        client.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    environment = sys.argv[1] if len(sys.argv) > 1 else "staging"
    test_mongodb_query(environment)
