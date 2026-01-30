"""
MongoDB Change Stream Watcher
Monitors MongoDB for new signals and processes them
"""

import time
import logging
import datetime
import os
import requests
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

        # DEBUG: Log the MongoDB URL being used
        logger.debug(f"🔧 Initializing MongoDBWatcher with URL: {mongodb_url}")
        logger.debug(f"🔧 Environment: {environment}")

        # Connect to MongoDB
        self.connect()

    def _build_leg_data(self, raw_signal_doc: dict, signal_array: list, leg_index: int) -> dict:
        """
        Build data for a single leg to be added to the legs array.

        Returns leg object that will be appended to the signal document's legs array.
        """
        # Build raw.legs from signal array
        raw_legs = []
        for leg in signal_array:
            raw_leg = {
                "instrument": leg.get('instrument') or leg.get('ticker'),
                "instrument_type": leg.get('instrument_type', 'STOCK'),
                "action": leg.get('action', 'UNKNOWN'),
                "direction": leg.get('direction', 'UNKNOWN'),
                "quantity": leg.get('quantity', 0),
                "order_type": leg.get('order_type', 'MARKET'),
                "price": leg.get('price', 0),
            }
            # Optional fields
            if leg.get('stop_loss'):
                raw_leg['stop_loss'] = leg['stop_loss']
            if leg.get('take_profit'):
                raw_leg['take_profit'] = leg['take_profit']
            if leg.get('strike'):
                raw_leg['strike'] = leg['strike']
            if leg.get('expiry'):
                raw_leg['expiry'] = leg['expiry']
            if leg.get('option_type'):
                raw_leg['option_type'] = leg['option_type']
            # Preserve nested option legs if provided (multi-leg option strategies)
            if leg.get('legs') and isinstance(leg.get('legs'), list):
                raw_leg['legs'] = leg['legs']
            raw_legs.append(raw_leg)

        # Determine leg_type from first leg's action (or signal_type if available)
        signal_type = raw_signal_doc.get('signal_type', 'ENTRY').upper()
        first_leg_action = signal_array[0].get('action', 'UNKNOWN').upper() if signal_array else 'UNKNOWN'

        # Use signal_type if available, otherwise infer from action
        if signal_type in ['ENTRY', 'EXIT', 'SCALE_IN', 'SCALE_OUT']:
            leg_type = signal_type
        elif first_leg_action in ['BUY', 'SELL', 'SHORT', 'COVER']:
            # Map action to leg_type (legacy support)
            leg_type = 'ENTRY' if first_leg_action in ['BUY', 'SHORT'] else 'EXIT'
        else:
            leg_type = 'UNKNOWN'

        # Generate leg_id: signal_id + "__" + leg_type (lowercase) + leg_index
        signal_id = raw_signal_doc['signalID']
        leg_id = f"{signal_id}__{leg_type.lower()}_{leg_index}"

        now = datetime.datetime.utcnow()
        return {
            "leg_id": leg_id,
            "leg_type": leg_type,
            "leg_index": leg_index,
            "raw": {
                "_id": raw_signal_doc['_id'],  # Reference to trading_signals_raw
                "received_at": raw_signal_doc.get('received_at', now),
                "sent_epoch": raw_signal_doc.get('signal_sent_EPOCH'),
                "entry_name": raw_signal_doc.get('entry_name'),
                "exit_name": raw_signal_doc.get('exit_name'),
                "entry_signal_id": raw_signal_doc.get('entry_signal_id'),  # ObjectId reference to parent ENTRY
                "account_equity": raw_signal_doc.get('account_equity'),
                "signal_type": signal_type,
                "legs": raw_legs
            },
            "decision": None,  # Will be populated by cerebro
            "execution": None,  # Will be populated by execution service
            "processing_timestamps": {
                "signal_received": raw_signal_doc.get('received_at', now),  # When signal was first received
                "signal_ingestion_processed": now,  # When signal_ingestion created this leg
                "cerebro_processed": None,  # Will be set by cerebro
                "execution_started": None,  # Will be set by execution service
                "execution_completed": None  # Will be set by execution service
            },
            "processing_lag": None,  # Will be calculated after execution completes
            "created_at": now
        }

    def _build_signal_store_doc(self, raw_signal_doc: dict, signal_array: list) -> dict:
        """
        Build a signal_store document using CONSOLIDATED schema.

        NEW APPROACH: ONE document per signal that contains ALL legs.
        - ENTRY leg creates the document
        - EXIT/SCALE legs are appended to the legs array

        This replaces the old approach of separate documents per leg.
        """
        signal_id = raw_signal_doc['signalID']
        signal_type = raw_signal_doc.get('signal_type', 'ENTRY').upper()

        # For EXIT signals, we need the parent signal ID
        is_exit_or_scale = signal_type in ['EXIT', 'SCALE_IN', 'SCALE_OUT']
        parent_signal_id = raw_signal_doc.get('entry_signal_id') if is_exit_or_scale else None

        if is_exit_or_scale and not parent_signal_id:
            self.logger.warning(f"EXIT/SCALE signal {signal_id} missing entry_signal_id - cannot link to parent")

        # Get instrument info from first leg
        first_leg = signal_array[0] if signal_array else {}
        instrument = first_leg.get('instrument') or first_leg.get('ticker')

        # Build the base signal document (for new ENTRY signals)
        return {
            # === IDENTITY ===
            "signal_id": signal_id,  # Signal ID from ENTRY leg
            "base_signal_id": signal_id,  # Same as signal_id for ENTRY, used to find parent for EXIT
            "entry_name": raw_signal_doc.get('entry_name'),  # entry_name for linking EXIT signals
            "strategy_id": raw_signal_doc['strategy_name'],
            "environment": raw_signal_doc.get('environment', 'production'),
            "account_type": raw_signal_doc.get('account_type'),  # Account type (mock, paper, live)
            "mode": raw_signal_doc.get('mode'),  # Trading mode (mock_mock, mock_live, paper_live, live_live)
            "data_source": raw_signal_doc.get('data_source', 'mock'),  # Data source for broker selection (mock or live)
            "instrument": instrument,

            # === LEGS ARRAY (ONE DOCUMENT PER SIGNAL!) ===
            "legs": [],  # Will be appended to

            # === POSITION STATUS ===
            "position": {
                "status": "PENDING",  # PENDING → OPEN → PARTIAL → CLOSED
                "entry_quantity": 0,
                "exit_quantity": 0,
                "remaining_quantity": 0,
                "pnl": None,
                "opened_at": None,
                "closed_at": None
            },

            # === METADATA ===
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }

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

                    # CONSOLIDATED SCHEMA: ONE document per signal
                    signal_type = raw_signal_doc.get('signal_type', 'ENTRY').upper()
                    is_exit_or_scale = signal_type in ['EXIT', 'SCALE_IN', 'SCALE_OUT']
                    parent_signal_id = raw_signal_doc.get('entry_signal_id') if is_exit_or_scale else None

                    if is_exit_or_scale and parent_signal_id:
                        # EXIT/SCALE: Find parent signal and append leg
                        # Try to find by entry_name first (matches entry_signal_id), fallback to base_signal_id
                        parent_doc = self.signal_store_collection.find_one({"entry_name": parent_signal_id})
                        if not parent_doc:
                            parent_doc = self.signal_store_collection.find_one({"base_signal_id": parent_signal_id})

                        if parent_doc:
                            # Calculate leg index
                            leg_index = len(parent_doc.get('legs', []))

                            # Build leg data
                            leg_data = self._build_leg_data(raw_signal_doc, signal_array, leg_index)

                            # Append leg to parent document
                            self.signal_store_collection.update_one(
                                {"_id": parent_doc['_id']},
                                {
                                    "$push": {"legs": leg_data},
                                    "$set": {"updated_at": datetime.datetime.utcnow()}
                                }
                            )

                            mathematricks_signal_id = parent_doc['_id']
                            logger.info(f"📝 Appended {signal_type} leg to signal_store document: {mathematricks_signal_id}")
                        else:
                            logger.error(f"❌ Parent signal {parent_signal_id} not found for EXIT/SCALE signal {raw_signal_doc['signalID']}")
                            # Skip this signal
                            continue
                    else:
                        # ENTRY: Create new signal document
                        # Check for duplicate signalID to prevent collisions
                        existing_signal = self.signal_store_collection.find_one({"signal_id": raw_signal_doc['signalID']})
                        if existing_signal:
                            logger.warning(f"⚠️ Duplicate signalID detected: {raw_signal_doc['signalID']} already exists in signal_store (ID: {existing_signal['_id']})")
                            logger.warning(f"   Skipping duplicate ENTRY signal. This may indicate a test data issue.")
                            # Use existing signal's ID instead of creating a new one
                            mathematricks_signal_id = existing_signal['_id']
                        else:
                            signal_store_doc = self._build_signal_store_doc(raw_signal_doc, signal_array)

                            # Add first leg (the ENTRY leg)
                            entry_leg = self._build_leg_data(raw_signal_doc, signal_array, 0)
                            signal_store_doc['legs'] = [entry_leg]

                            # Insert into signal_store
                            result = self.signal_store_collection.insert_one(signal_store_doc)
                            mathematricks_signal_id = result.inserted_id

                            logger.info(f"📝 Created new signal_store document: {mathematricks_signal_id} for ENTRY signal {raw_signal_doc['signalID']}")

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
                        'account_equity': raw_signal_doc.get('account_equity'),  # For ratio-based position sizing
                        'environment': raw_signal_doc.get('environment', 'production'),
                        'account_type': raw_signal_doc.get('account_type'),  # For account routing
                        'data_source': raw_signal_doc.get('data_source', 'mock'),  # For broker selection
                        'mode': raw_signal_doc.get('mode'),  # For broker selection
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
                logger.debug(f"🔗 MongoDB URL: {self.mongodb_url}")
                logger.debug(f"📊 Watching: {self.mongodb_collection.database.name}.{self.mongodb_collection.name}")
                logger.debug(f"🎯 Environment filter: {self.environment}")

                for change in stream:
                    logger.debug(f"🔔 Change stream event received! Type: {change.get('operationType')}")
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
                            logger.info(f"⏭️ Skipping already processed signal: {raw_signal_doc.get('signalID')}")
                            continue

                        # Filter by environment
                        document_environment = raw_signal_doc.get('environment', 'unknown')
                        if document_environment != self.environment:
                            # Ignore signals from other environments
                            logger.info(f"⏭️ Skipping signal from {document_environment} environment (expecting {self.environment})")
                            continue

                        # Must have signalID (valid signal)
                        if 'signalID' not in raw_signal_doc:
                            logger.info("⏭️ Skipping document without signalID")
                            continue

                        # Get signal array (new format)
                        signal_array = raw_signal_doc.get('signal', [])
                        if not signal_array or not isinstance(signal_array, list) or len(signal_array) == 0:
                            logger.warning(f"⚠️ Invalid signal array for {raw_signal_doc.get('signalID')}")
                            continue

                        # CONSOLIDATED SCHEMA: ONE document per signal
                        signal_type = raw_signal_doc.get('signal_type', 'ENTRY').upper()
                        is_exit_or_scale = signal_type in ['EXIT', 'SCALE_IN', 'SCALE_OUT']
                        parent_signal_id = raw_signal_doc.get('entry_signal_id') if is_exit_or_scale else None

                        if is_exit_or_scale and parent_signal_id:
                            # EXIT/SCALE: Find parent signal  
                            # Try multiple lookup methods:
                            # 1. If it's a 24-char hex ObjectId → lookup by _id
                            # 2. Otherwise → lookup by signal_id field (string)
                            # 3. Fallback: entry_name or base_signal_id (for old data)
                            parent_doc = None
                            
                            # Try ObjectId first if it looks like one
                            if len(parent_signal_id) == 24 and all(c in '0123456789abcdefABCDEF' for c in parent_signal_id):
                                try:
                                    from bson import ObjectId
                                    parent_doc = self.signal_store_collection.find_one({"_id": ObjectId(parent_signal_id)})
                                    if parent_doc:
                                        logger.info(f"✅ Found parent signal by ObjectId: {parent_doc.get('signal_id')}")
                                except:
                                    pass
                            
                            # Try signal_id string lookup
                            if not parent_doc:
                                parent_doc = self.signal_store_collection.find_one({"signal_id": parent_signal_id})
                                if parent_doc:
                                    logger.info(f"✅ Found parent signal by signal_id: {parent_doc.get('signal_id')}")
                            
                            # Fallback: old methods (entry_name, base_signal_id)
                            if not parent_doc:
                                parent_doc = self.signal_store_collection.find_one({"entry_name": parent_signal_id})
                            if not parent_doc:
                                parent_doc = self.signal_store_collection.find_one({"base_signal_id": parent_signal_id})

                            if parent_doc:
                                # Calculate leg index
                                leg_index = len(parent_doc.get('legs', []))

                                # Build leg data
                                leg_data = self._build_leg_data(raw_signal_doc, signal_array, leg_index)

                                # Append leg to parent document
                                self.signal_store_collection.update_one(
                                    {"_id": parent_doc['_id']},
                                    {
                                        "$push": {"legs": leg_data},
                                        "$set": {"updated_at": datetime.datetime.utcnow()}
                                    }
                                )

                                mathematricks_signal_id = parent_doc['_id']
                                logger.info(f"📝 Appended {signal_type} leg to signal_store document: {mathematricks_signal_id}")
                            else:
                                logger.error(f"❌ Parent signal {parent_signal_id} not found for {signal_type} signal {raw_signal_doc['signalID']}")
                                # Skip this signal
                                continue
                        else:
                            # ENTRY: Create new signal document
                            # Check for duplicate signalID to prevent collisions
                            existing_signal = self.signal_store_collection.find_one({"signal_id": raw_signal_doc['signalID']})
                            if existing_signal:
                                logger.warning(f"⚠️ Duplicate signalID detected: {raw_signal_doc['signalID']} already exists in signal_store (ID: {existing_signal['_id']})")
                                logger.warning(f"   Skipping duplicate ENTRY signal. This may indicate a test data issue.")
                                # Use existing signal's ID instead of creating a new one
                                mathematricks_signal_id = existing_signal['_id']
                            else:
                                signal_store_doc = self._build_signal_store_doc(raw_signal_doc, signal_array)

                                # Add first leg (the ENTRY leg)
                                entry_leg = self._build_leg_data(raw_signal_doc, signal_array, 0)
                                signal_store_doc['legs'] = [entry_leg]

                                # Insert into signal_store
                                result = self.signal_store_collection.insert_one(signal_store_doc)
                                mathematricks_signal_id = result.inserted_id

                                logger.info(f"📝 Created new signal_store document: {mathematricks_signal_id} for ENTRY signal {raw_signal_doc['signalID']}")

                        # UPDATE trading_signals_raw with link
                        self.mongodb_collection.update_one(
                            {"_id": raw_signal_doc['_id']},
                            {"$set": {"mathematricks_signal_id": mathematricks_signal_id}}
                        )

                        # ============================================================
                        # CALL CEREBRO API (Direct API call with retry logic)
                        # ============================================================
                        cerebro_success = False
                        max_retries = 3
                        retry_delays = [0.5, 2, 5]  # exponential backoff
                        
                        for attempt in range(max_retries):
                            try:
                                cerebro_url = os.getenv('CEREBRO_SERVICE_URL', 'http://cerebro-service:8082')
                                api_endpoint = f"{cerebro_url}/api/v1/process-signal"
                                
                                payload = {
                                    "signal_store_id": str(mathematricks_signal_id),
                                    "leg_index": leg_index if is_exit_or_scale else 0
                                }
                                
                                if attempt == 0:
                                    logger.info(f"📤 Calling Cerebro API: {api_endpoint}")
                                else:
                                    logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for Cerebro API")
                                logger.debug(f"   Payload: {payload}")
                                
                                # Timeout: 5 seconds for first attempt, 10s for retries
                                timeout = 10 if attempt > 0 else 5
                                response = requests.post(
                                    api_endpoint,
                                    json=payload,
                                    timeout=timeout
                                )
                                
                                # Check if request was accepted
                                if response.status_code == 200:
                                    logger.info(f"✅ Cerebro API accepted signal")
                                    cerebro_success = True
                                    break
                                else:
                                    logger.warning(f"⚠️ Cerebro API returned status {response.status_code}")
                                    if attempt < max_retries - 1:
                                        time.sleep(retry_delays[attempt])
                                
                            except requests.exceptions.ConnectionError as e:
                                logger.warning(f"⚠️ Cerebro connection failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                                if attempt < max_retries - 1:
                                    logger.info(f"   Retrying in {retry_delays[attempt]}s...")
                                    time.sleep(retry_delays[attempt])
                                else:
                                    logger.error(f"❌ Cerebro not available after {max_retries} attempts")
                                    logger.error(f"   Signal {raw_signal_doc['signalID']} may not be processed by Cerebro!")
                            except requests.exceptions.Timeout:
                                # Timeout is OK - Cerebro is processing, just took >timeout to respond
                                logger.info(f"⏱️ Cerebro API timeout (processing in background)")
                                cerebro_success = True  # Consider this a success
                                break
                            except requests.exceptions.RequestException as e:
                                logger.error(f"❌ Failed to call Cerebro API: {str(e)}")
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delays[attempt])
                                else:
                                    logger.error(f"   Signal {raw_signal_doc['signalID']} may not be processed by Cerebro!")
                            except Exception as e:
                                logger.error(f"❌ Unexpected error calling Cerebro API: {str(e)}", exc_info=True)
                                break

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
                            'account_equity': raw_signal_doc.get('account_equity'),  # For ratio-based position sizing
                            'environment': raw_signal_doc.get('environment', 'production'),
                            'account_type': raw_signal_doc.get('account_type'),  # For account routing
                            'data_source': raw_signal_doc.get('data_source', 'mock'),  # For broker selection
                            'mode': raw_signal_doc.get('mode'),  # For broker selection
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
