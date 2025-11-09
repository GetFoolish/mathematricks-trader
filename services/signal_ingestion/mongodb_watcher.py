"""
MongoDB Change Stream Watcher
Monitors MongoDB for new signals and processes them
"""

import time
import logging
import datetime
from typing import Optional, Callable
from dateutil import parser
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger('signal_ingestion.mongodb_watcher')


class MongoDBWatcher:
    """
    Watches MongoDB Change Streams for new trading signals
    Handles connection resilience and retry logic
    """

    def __init__(self, mongodb_url: str, environment: str = 'production'):
        self.mongodb_url = mongodb_url
        self.environment = environment
        self.mongodb_client = None
        self.mongodb_collection = None
        self.resume_token = None
        self.last_signal_timestamp = None
        self.signal_callback = None

        # Connect to MongoDB
        self.connect()

    def connect(self) -> bool:
        """Connect to MongoDB Atlas"""
        try:
            self.mongodb_client = MongoClient(
                self.mongodb_url,
                tls=True,
                tlsAllowInvalidCertificates=True  # For development only
            )
            # Test connection
            self.mongodb_client.admin.command('ping')

            # Get collection
            db = self.mongodb_client['mathematricks_signals']
            self.mongodb_collection = db['trading_signals']

            logger.info("✅ Connected to MongoDB Atlas")
            return True
        except PyMongoError as e:
            logger.error(f"⚠️ MongoDB connection failed: {e}")
            return False

    def set_signal_callback(self, callback: Callable):
        """Set the callback function to process new signals"""
        self.signal_callback = callback

    def fetch_missed_signals(self):
        """Fetch missed signals directly from MongoDB (catch-up mode)"""
        if self.mongodb_collection is None:
            logger.error("❌ MongoDB not available - cannot fetch missed signals")
            return

        try:
            logger.info("🔄 Checking for missed signals from MongoDB...")

            # Build query filter - only get signals for this environment
            query_filter = {
                'signal_processed': {'$ne': True},  # Only get unprocessed signals
                'environment': self.environment  # Only get signals for this environment
            }
            if self.last_signal_timestamp:
                try:
                    since_dt = parser.parse(self.last_signal_timestamp)
                    query_filter['received_at'] = {'$gt': since_dt}
                except Exception as e:
                    logger.warning(f"⚠️ Invalid timestamp format: {self.last_signal_timestamp}")

            # Query MongoDB directly for unprocessed signals
            missed_signals_cursor = self.mongodb_collection.find(query_filter).sort('received_at', 1)
            missed_signals = list(missed_signals_cursor)

            if missed_signals:
                logger.info(f"📥 Found {len(missed_signals)} missed signals in MongoDB")

                for signal_doc in missed_signals:
                    # Convert MongoDB document to signal format
                    received_time = signal_doc['received_at']
                    if isinstance(received_time, str):
                        received_time = parser.parse(received_time)

                    signal_data = {
                        'timestamp': signal_doc.get('timestamp'),
                        'signalID': signal_doc.get('signalID'),
                        'signal_sent_EPOCH': signal_doc.get('signal_sent_EPOCH'),
                        'strategy_name': signal_doc.get('strategy_name', 'Unknown Strategy'),
                        'signal': signal_doc.get('signal', {}),
                        'environment': signal_doc.get('environment', 'production')
                    }

                    # Process via callback
                    if self.signal_callback:
                        self.signal_callback(
                            signal_data,
                            received_time,
                            is_catchup=True,
                            original_id=signal_doc.get('signal_id')
                        )

                    # Mark signal as processed
                    self.mark_signal_processed(signal_doc['_id'])

                logger.info(f"✅ Successfully caught up with {len(missed_signals)} signals from MongoDB")
            else:
                logger.info("✅ No missed signals found in MongoDB")

        except PyMongoError as e:
            logger.error(f"❌ Error fetching from MongoDB: {e}")
            logger.error("💡 Check MongoDB connection or restart collector")

    def mark_signal_processed(self, signal_id):
        """Mark a signal as processed in MongoDB (async, low priority)"""
        if self.mongodb_collection is None:
            return

        try:
            self.mongodb_collection.update_one(
                {'_id': signal_id},
                {'$set': {'signal_processed': True}},
                upsert=False
            )
        except PyMongoError:
            # Silently fail - this is low priority
            pass

    def watch_for_new_signals(self) -> bool:
        """Watch for new signals using MongoDB Change Streams"""
        if self.mongodb_collection is None:
            logger.error("❌ MongoDB not available - cannot watch for new signals")
            return False

        try:
            # Start watching with resume token if we have one
            watch_options = {}
            if self.resume_token:
                watch_options['resume_after'] = self.resume_token
                logger.info("🔄 Resuming from previous position")

            # Open change stream
            with self.mongodb_collection.watch([], **watch_options) as stream:
                logger.info(f"✅ Change Stream connected - waiting for {self.environment} signals only...")

                for change in stream:
                    try:
                        # Update resume token for reconnection resilience
                        self.resume_token = stream.resume_token

                        # Only process insert operations (new signals)
                        if change.get('operationType') != 'insert':
                            continue

                        # Extract the new document
                        new_document = change.get('fullDocument')
                        if not new_document:
                            logger.warning("⚠️ No document in change event")
                            continue

                        # Filter by environment
                        document_environment = new_document.get('environment', 'unknown')
                        if document_environment != self.environment:
                            # Ignore signals from other environments
                            continue

                        # Convert to signal format
                        received_time = new_document['received_at']
                        if isinstance(received_time, str):
                            received_time = parser.parse(received_time)

                        signal_data = {
                            'timestamp': new_document.get('timestamp'),
                            'signalID': new_document.get('signalID'),
                            'signal_sent_EPOCH': new_document.get('signal_sent_EPOCH'),
                            'strategy_name': new_document.get('strategy_name', 'Unknown Strategy'),
                            'signal': new_document.get('signal', {}),
                            'environment': new_document.get('environment', 'production')
                        }

                        # Process via callback
                        if self.signal_callback:
                            self.signal_callback(
                                signal_data,
                                received_time,
                                is_catchup=False,
                                original_id=new_document.get('signal_id')
                            )

                        # Mark signal as processed
                        self.mark_signal_processed(new_document['_id'])

                    except Exception as e:
                        logger.error(f"⚠️ Error processing change stream event: {e}")
                        continue

        except PyMongoError as e:
            logger.error(f"❌ Change Stream error: {e}")
            logger.error("🔄 Will retry connection...")
            return False
        except Exception as e:
            logger.error(f"💥 Unexpected error in Change Stream: {e}")
            return False

        return True

    def start_with_retry(self, max_retries: int = 5, base_delay: int = 2):
        """Start Change Stream with automatic retry logic"""
        retry_count = 0

        # PHASE 1: Catch-up mode
        logger.info("\n🔄 PHASE 1: Catch-up Mode")
        if self.mongodb_collection is not None:
            self.fetch_missed_signals()
        else:
            logger.error("❌ MongoDB connection failed - cannot start monitoring")
            logger.error("💡 Restart the collector to retry MongoDB connection")
            return

        # PHASE 2: Real-time mode
        logger.info("\n📡 PHASE 2: Real-Time Mode - Change Streams")

        while retry_count < max_retries:
            try:
                if self.watch_for_new_signals():
                    # If we get here, the stream ended normally
                    logger.info("🔄 Change Stream ended, restarting...")
                else:
                    # Connection failed, implement exponential backoff
                    retry_count += 1
                    delay = base_delay * (2 ** retry_count)
                    logger.info(f"⏰ Retrying in {delay} seconds... (attempt {retry_count}/{max_retries})")
                    time.sleep(delay)

            except KeyboardInterrupt:
                logger.info("\n🛑 Change Stream monitoring stopped by user")
                break
            except Exception as e:
                retry_count += 1
                delay = base_delay * (2 ** retry_count)
                logger.error(f"💥 Unexpected error: {e}")
                logger.info(f"⏰ Retrying in {delay} seconds... (attempt {retry_count}/{max_retries})")
                time.sleep(delay)

        if retry_count >= max_retries:
            logger.error(f"❌ Failed to establish stable Change Stream after {max_retries} attempts")
            logger.error("💡 Check MongoDB connection and restart collector")
