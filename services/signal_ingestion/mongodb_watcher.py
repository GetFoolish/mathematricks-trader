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
        self.signal_store_collection = None
        self.resume_token = None
        self.last_signal_timestamp = None
        self.signal_callback = None

        # Connect to MongoDB
        self.connect()

    def connect(self) -> bool:
        """Connect to MongoDB"""
        try:
            # Only use TLS for remote MongoDB Atlas connections
            use_tls = 'mongodb+srv' in self.mongodb_url or 'mongodb.net' in self.mongodb_url
            if use_tls:
                self.mongodb_client = MongoClient(
                    self.mongodb_url,
                    tls=True,
                    tlsAllowInvalidCertificates=True  # For development only
                )
            else:
                self.mongodb_client = MongoClient(self.mongodb_url)
            # Test connection
            self.mongodb_client.admin.command('ping')

            # Get collection (Phase 7: Consolidated into mathematricks_trading)
            db = self.mongodb_client['mathematricks_trading']
            self.mongodb_collection = db['trading_signals_raw']
            self.signal_store_collection = db['signal_store']

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

            # Build query filter - only get signals without mathematricks_signal_id (unprocessed)
            query_filter = {
                'mathematricks_signal_id': {'$exists': False},  # Not yet processed
                'environment': self.environment,  # Only get signals for this environment
                'signalID': {'$exists': True}  # Only original signals
            }
            if self.last_signal_timestamp:
                try:
                    since_dt = parser.parse(self.last_signal_timestamp)
                    query_filter['received_at'] = {'$gt': since_dt}
                except Exception as e:
                    logger.warning(f"⚠️ Invalid timestamp format: {self.last_signal_timestamp}")

            # Query trading_signals_raw for unprocessed signals
            missed_signals_cursor = self.mongodb_collection.find(query_filter).sort('received_at', 1)
            missed_signals = list(missed_signals_cursor)

            if missed_signals:
                logger.info(f"📥 Found {len(missed_signals)} missed signals in MongoDB")

                for raw_signal_doc in missed_signals:
                    # Get signal array
                    signal_array = raw_signal_doc.get('signal', [])
                    if not signal_array or not isinstance(signal_array, list) or len(signal_array) == 0:
                        logger.warning(f"⚠️ Invalid signal array for {raw_signal_doc.get('signalID')}, skipping")
                        continue

                    first_leg = signal_array[0]

                    # CREATE NEW DOCUMENT IN signal_store
                    signal_store_doc = {
                        "raw_signal_id": raw_signal_doc['_id'],
                        "signal_id": raw_signal_doc['signalID'],
                        "strategy_id": raw_signal_doc['strategy_name'],
                        "instrument": first_leg.get('instrument') or first_leg.get('ticker'),
                        "direction": first_leg.get('direction', 'UNKNOWN'),
                        "action": first_leg.get('action', 'UNKNOWN'),
                        "signal_data": raw_signal_doc,

                        # Lifecycle fields (populated later)
                        "cerebro_decision": None,
                        "execution": None,
                        "position_status": None,
                        "exit_signals": [],
                        "pnl_realized": None,

                        # Timestamps
                        "created_at": datetime.datetime.utcnow(),
                        "updated_at": datetime.datetime.utcnow(),
                        "environment": raw_signal_doc.get('environment', 'production')
                    }

                    # Insert into signal_store
                    result = self.signal_store_collection.insert_one(signal_store_doc)
                    mathematricks_signal_id = result.inserted_id

                    logger.info(f"📝 Created signal_store document: {mathematricks_signal_id} for signal {raw_signal_doc['signalID']}")

                    # UPDATE trading_signals_raw with link
                    self.mongodb_collection.update_one(
                        {"_id": raw_signal_doc['_id']},
                        {"$set": {"mathematricks_signal_id": mathematricks_signal_id}}
                    )

                    # Convert MongoDB document to signal format
                    received_time = raw_signal_doc['received_at']
                    if isinstance(received_time, str):
                        received_time = parser.parse(received_time)

                    # Ensure received_time is timezone-aware (assume UTC if naive)
                    if received_time.tzinfo is None:
                        import datetime as dt
                        received_time = received_time.replace(tzinfo=dt.timezone.utc)

                    signal_data = {
                        'timestamp': raw_signal_doc.get('timestamp'),
                        'signalID': raw_signal_doc.get('signalID'),
                        'signal_sent_EPOCH': raw_signal_doc.get('signal_sent_EPOCH'),
                        'strategy_name': raw_signal_doc.get('strategy_name', 'Unknown Strategy'),
                        'signal': raw_signal_doc.get('signal', {}),
                        'signal_type': raw_signal_doc.get('signal_type'),
                        'entry_signal_id': raw_signal_doc.get('entry_signal_id'),  # For EXIT signals
                        'environment': raw_signal_doc.get('environment', 'production'),
                        'mathematricks_signal_id': str(mathematricks_signal_id)
                    }

                    # Process via callback
                    if self.signal_callback:
                        self.signal_callback(
                            signal_data,
                            received_time,
                            is_catchup=True,
                            mongodb_object_id=raw_signal_doc['_id']
                        )

                    # Mark signal as processed (updates trading_signals_raw)
                    self.mark_signal_processed(raw_signal_doc['_id'])

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

    def watch_for_new_signals(self) -> str:
        """
        Watch for new signals using MongoDB Change Streams
        Returns: 'success', 'token_reset', or 'error'
        """
        if self.mongodb_collection is None:
            logger.error("❌ MongoDB not available - cannot watch for new signals")
            return 'error'

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

                        # Extract the new document from trading_signals_raw
                        raw_signal_doc = change.get('fullDocument')
                        if not raw_signal_doc:
                            logger.warning("⚠️ No document in change event")
                            continue

                        # Skip if already processed (has mathematricks_signal_id)
                        if 'mathematricks_signal_id' in raw_signal_doc:
                            logger.debug("⏭️ Skipping already processed signal")
                            continue

                        # Filter by environment
                        document_environment = raw_signal_doc.get('environment', 'unknown')
                        if document_environment != self.environment:
                            # Ignore signals from other environments
                            continue

                        # Must have signalID (valid signal)
                        if 'signalID' not in raw_signal_doc:
                            logger.debug("⏭️ Skipping document without signalID")
                            continue

                        # Get signal array (new format)
                        signal_array = raw_signal_doc.get('signal', [])
                        if not signal_array or not isinstance(signal_array, list) or len(signal_array) == 0:
                            logger.warning(f"⚠️ Invalid signal array for {raw_signal_doc.get('signalID')}")
                            continue

                        first_leg = signal_array[0]

                        # CREATE NEW DOCUMENT IN signal_store
                        signal_store_doc = {
                            "raw_signal_id": raw_signal_doc['_id'],
                            "signal_id": raw_signal_doc['signalID'],
                            "strategy_id": raw_signal_doc['strategy_name'],
                            "instrument": first_leg.get('instrument') or first_leg.get('ticker'),
                            "direction": first_leg.get('direction', 'UNKNOWN'),
                            "action": first_leg.get('action', 'UNKNOWN'),
                            "signal_data": raw_signal_doc,  # Full raw signal

                            # Lifecycle fields (populated later by cerebro/execution)
                            "cerebro_decision": None,
                            "execution": None,
                            "position_status": None,
                            "exit_signals": [],
                            "pnl_realized": None,

                            # Timestamps
                            "created_at": datetime.datetime.utcnow(),
                            "updated_at": datetime.datetime.utcnow(),
                            "environment": raw_signal_doc.get('environment', 'production')
                        }

                        # Insert into signal_store
                        result = self.signal_store_collection.insert_one(signal_store_doc)
                        mathematricks_signal_id = result.inserted_id

                        logger.info(f"📝 Created signal_store document: {mathematricks_signal_id} for signal {raw_signal_doc['signalID']}")

                        # UPDATE trading_signals_raw with link
                        self.mongodb_collection.update_one(
                            {"_id": raw_signal_doc['_id']},
                            {"$set": {"mathematricks_signal_id": mathematricks_signal_id}}
                        )

                        # Convert to signal format for callback
                        received_time = raw_signal_doc['received_at']
                        if isinstance(received_time, str):
                            received_time = parser.parse(received_time)

                        # Ensure received_time is timezone-aware (assume UTC if naive)
                        if received_time.tzinfo is None:
                            import datetime as dt
                            received_time = received_time.replace(tzinfo=dt.timezone.utc)

                        signal_data = {
                            'timestamp': raw_signal_doc.get('timestamp'),
                            'signalID': raw_signal_doc.get('signalID'),
                            'signal_sent_EPOCH': raw_signal_doc.get('signal_sent_EPOCH'),
                            'strategy_name': raw_signal_doc.get('strategy_name', 'Unknown Strategy'),
                            'signal': raw_signal_doc.get('signal', {}),
                            'signal_type': raw_signal_doc.get('signal_type'),
                            'entry_signal_id': raw_signal_doc.get('entry_signal_id'),  # For EXIT signals
                            'environment': raw_signal_doc.get('environment', 'production'),
                            'mathematricks_signal_id': str(mathematricks_signal_id)  # Pass to signal_ingestion
                        }

                        # Process via callback
                        if self.signal_callback:
                            self.signal_callback(
                                signal_data,
                                received_time,
                                is_catchup=False,
                                mongodb_object_id=raw_signal_doc['_id']
                            )

                        # Mark signal as processed
                        self.mark_signal_processed(raw_signal_doc['_id'])

                    except Exception as e:
                        logger.error(f"⚠️ Error processing change stream event: {e}")
                        continue

        except PyMongoError as e:
            error_code = getattr(e, 'code', None)

            # Handle invalid resume token (code 260) - reset and retry immediately
            if error_code == 260:
                logger.warning(f"⚠️ Invalid resume token detected - resetting...")
                self.resume_token = None  # Clear invalid token
                return 'token_reset'  # Signal immediate retry without backoff

            logger.error(f"❌ Change Stream error: {e}")
            logger.error("🔄 Will retry connection...")
            return 'error'
        except Exception as e:
            logger.error(f"💥 Unexpected error in Change Stream: {e}")
            return 'error'

        return 'success'

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
                result = self.watch_for_new_signals()

                if result == 'success':
                    # Stream ended normally, restart immediately
                    logger.info("🔄 Change Stream ended, restarting...")
                    retry_count = 0  # Reset counter on success
                elif result == 'token_reset':
                    # Invalid token was cleared, retry immediately without backoff
                    logger.info("🔄 Retrying with fresh connection (no resume token)...")
                    # Don't increment retry_count or sleep
                else:  # 'error'
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
