#!/usr/bin/env python3
import json
import time
import datetime
import os
import logging
from dateutil import parser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import Pub/Sub for MVP microservices bridge
try:
    from google.cloud import pubsub_v1
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False

# Setup logging with custom formatters
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File handler with detailed format
file_handler = logging.FileHandler('logs/signal_collector.log')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(levelname)s | %(asctime)s | %(message)s | %(filename)s | %(lineno)d',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Console handler with simple format (message only)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)

# Signal processing handler - unified log for signal journey
signal_processing_handler = logging.FileHandler('logs/signal_processing.log')
signal_processing_handler.setLevel(logging.INFO)
signal_processing_formatter = logging.Formatter(
    '%(asctime)s | [COLLECTOR] | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
signal_processing_handler.setFormatter(signal_processing_formatter)
# Only log signal-related events to this file (filtered later)
signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage())

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.addHandler(signal_processing_handler)

class WebhookSignalCollector:
    def __init__(self, webhook_url: str, local_port: int = 8888, mongodb_url: str = None):
        self.webhook_url = webhook_url
        self.local_port = local_port
        self.collected_signals = []
        self.server = None
        self.last_signal_timestamp = None
        self.resume_token = None
        self.mongodb_url = mongodb_url or "mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/"
        self.mongodb_client = None
        self.mongodb_collection = None

        # Try to connect to MongoDB
        self.connect_to_mongodb()

        # Initialize Pub/Sub publisher for MVP microservices
        self.pubsub_publisher = None
        self.pubsub_topic_path = None
        if PUBSUB_AVAILABLE:
            try:
                project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
                self.pubsub_publisher = pubsub_v1.PublisherClient()
                self.pubsub_topic_path = self.pubsub_publisher.topic_path(project_id, 'standardized-signals')
                logger.info("✅ Pub/Sub bridge enabled - signals will route to microservices")
            except Exception as e:
                logger.info(f"⚠️  Pub/Sub initialization failed: {e}")
                self.pubsub_publisher = None

    def connect_to_mongodb(self):
        """Connect to MongoDB Atlas"""
        try:
            # Add SSL options for macOS compatibility
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
            logger.info(f"⚠️ MongoDB connection failed: {e}")
            logger.info("📄 Will fall back to JSON file storage")
            return False

    def fetch_missed_signals_from_mongodb(self):
        """Fetch missed signals directly from MongoDB"""
        if self.mongodb_collection is None:
            logger.info("❌ MongoDB not available - cannot fetch missed signals")
            return

        try:
            logger.info("🔄 Checking for missed signals from MongoDB...")

            # Determine environment filter based on webhook URL
            environment = "staging" if "staging" in self.webhook_url else "production"

            # Build query filter - only get signals for this environment
            query_filter = {
                'signal_processed': {'$ne': True},  # Only get unprocessed signals
                'environment': environment  # Only get signals for this environment
            }
            if self.last_signal_timestamp:
                try:
                    since_dt = parser.parse(self.last_signal_timestamp)
                    query_filter['received_at'] = {'$gt': since_dt}
                except Exception as e:
                    logger.info(f"⚠️ Invalid timestamp format: {self.last_signal_timestamp}")

            # Query MongoDB directly for unprocessed signals
            missed_signals_cursor = self.mongodb_collection.find(query_filter).sort('received_at', 1)
            missed_signals = list(missed_signals_cursor)

            if missed_signals:
                logger.info(f"📥 Found {len(missed_signals)} missed signals in MongoDB")

                for signal_doc in missed_signals:
                    # Convert MongoDB document to our format
                    received_time = signal_doc['received_at']
                    if isinstance(received_time, str):
                        received_time = parser.parse(received_time)

                    # Reconstruct signal data from MongoDB format
                    signal_data = {
                        'timestamp': signal_doc.get('timestamp'),
                        'signalID': signal_doc.get('signalID'),
                        'signal_sent_EPOCH': signal_doc.get('signal_sent_EPOCH'),
                        'strategy_name': signal_doc.get('strategy_name', 'Unknown Strategy'),
                        'signal': signal_doc.get('signal', {}),
                        'environment': signal_doc.get('environment', 'production')  # Include environment field
                    }

                    # Process as a caught-up signal
                    self.process_signal(
                        signal_data,
                        received_time,
                        is_catchup=True,
                        original_id=signal_doc.get('signal_id')
                    )

                    # Mark signal as processed (async, low priority)
                    self.mark_signal_processed(signal_doc['_id'])

                logger.info(f"✅ Successfully caught up with {len(missed_signals)} signals from MongoDB")
            else:
                logger.info("✅ No missed signals found in MongoDB")

        except PyMongoError as e:
            logger.info(f"❌ Error fetching from MongoDB: {e}")
            logger.info("💡 Check MongoDB connection or restart collector")

    def mark_signal_processed(self, signal_id):
        """Mark a signal as processed in MongoDB (async, low priority)"""
        if self.mongodb_collection is None:
            return

        try:
            # Use update_one to set the processed flag
            self.mongodb_collection.update_one(
                {'_id': signal_id},
                {'$set': {'signal_processed': True}},
                upsert=False
            )
        except PyMongoError:
            # Silently fail - this is low priority and shouldn't interfere with signal processing
            pass

    def watch_for_new_signals(self):
        """Watch for new signals using MongoDB Change Streams"""
        if self.mongodb_collection is None:
            logger.info("❌ MongoDB not available - cannot watch for new signals")
            return

        try:

            # Start watching with resume token if we have one
            watch_options = {}
            if self.resume_token:
                watch_options['resume_after'] = self.resume_token
                logger.info(f"🔄 Resuming from previous position")

            # Determine which environment we're monitoring
            expected_environment = "staging" if "staging" in self.webhook_url else "production"

            # Open change stream (watch all operations - we only insert anyway)
            with self.mongodb_collection.watch([], **watch_options) as stream:
                logger.info(f"✅ Change Stream connected - waiting for {expected_environment} signals only...")

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
                            logger.info("⚠️ No document in change event")
                            continue

                        # Filter by environment - only process signals for this environment
                        document_environment = new_document.get('environment', 'unknown')
                        expected_environment = "staging" if "staging" in self.webhook_url else "production"

                        if document_environment != expected_environment:
                            # Ignore signals from other environments
                            continue

                        # Convert to our signal format
                        received_time = new_document['received_at']
                        if isinstance(received_time, str):
                            received_time = parser.parse(received_time)

                        # Reconstruct signal data from MongoDB format
                        signal_data = {
                            'timestamp': new_document.get('timestamp'),
                            'signalID': new_document.get('signalID'),
                            'signal_sent_EPOCH': new_document.get('signal_sent_EPOCH'),
                            'strategy_name': new_document.get('strategy_name', 'Unknown Strategy'),
                            'signal': new_document.get('signal', {}),
                            'environment': new_document.get('environment', 'production')  # Include environment field
                        }

                        # Process as live signal
                        self.process_signal(
                            signal_data,
                            received_time,
                            is_catchup=False,
                            original_id=new_document.get('signal_id')
                        )

                        # Mark signal as processed (safe since Change Stream only watches INSERTs)
                        self.mark_signal_processed(new_document['_id'])

                    except Exception as e:
                        logger.info(f"⚠️ Error processing change stream event: {e}")
                        continue

        except PyMongoError as e:
            logger.info(f"❌ Change Stream error: {e}")
            logger.info("🔄 Will retry connection...")
            return False
        except Exception as e:
            logger.info(f"💥 Unexpected error in Change Stream: {e}")
            return False

        return True

    def start_change_stream_with_retry(self):
        """Start Change Stream with automatic retry logic"""
        retry_count = 0
        max_retries = 5
        base_delay = 2

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
                logger.info(f"💥 Unexpected error: {e}")
                logger.info(f"⏰ Retrying in {delay} seconds... (attempt {retry_count}/{max_retries})")
                time.sleep(delay)

        if retry_count >= max_retries:
            logger.info(f"❌ Failed to establish stable Change Stream after {max_retries} attempts")
            logger.info("💡 Check MongoDB connection and restart collector")



    def calculate_delay(self, sent_timestamp: str, received_timestamp: datetime.datetime) -> float:
        """Calculate delay between sent and received timestamps"""
        try:
            # Handle None or empty timestamp
            if not sent_timestamp or sent_timestamp == 'No timestamp':
                return 0.0

            sent_dt = parser.parse(sent_timestamp)

            # Make both timestamps timezone-aware
            if sent_dt.tzinfo is None:
                # Assume UTC if no timezone info
                sent_dt = sent_dt.replace(tzinfo=datetime.timezone.utc)
            if received_timestamp.tzinfo is None:
                # Make received timestamp UTC timezone-aware
                received_timestamp = received_timestamp.replace(tzinfo=datetime.timezone.utc)

            delay_seconds = (received_timestamp - sent_dt).total_seconds()
            return delay_seconds
        except Exception as e:
            logger.info(f"⚠️ Error calculating delay: {e}")
            return 0.0

    def process_signal(self, signal_data: dict, received_time: datetime.datetime, is_catchup: bool = False, original_id: int = None):
        """Process and display received signal with timing information"""
        signal_id = original_id if is_catchup else len(self.collected_signals) + 1

        # Extract signal information
        timestamp = signal_data.get('timestamp', 'No timestamp')
        signal = signal_data.get('signal', {})
        strategy_name = signal_data.get('strategy_name', 'Unknown Strategy')

        # Get signal ID from the data
        signal_id_from_data = signal_data.get('signal_id') or signal_data.get('signalID')

        # Calculate delay if timestamp is provided
        delay = 0.0
        if timestamp and timestamp != 'No timestamp':
            delay = self.calculate_delay(timestamp, received_time)

        # Store signal in memory for display (no file saving)
        signal_record = {
            'id': signal_id,
            'received_time': received_time,
            'sent_timestamp': timestamp,
            'delay_seconds': delay,
            'signal': signal_data,
            'is_catchup': is_catchup
        }
        self.collected_signals.append(signal_record)

        # Display signal information - simplified format
        signal_type = "📥 CATCHUP" if is_catchup else "🔥 REAL-TIME SIGNAL DETECTED!"
        logger.info(f"\n{signal_type}")
        logger.info(f"📊 Strategy: {strategy_name}")
        if delay > 0:
            logger.info(f"⚡ Delay: {delay:.3f} seconds")
        if signal_id_from_data:
            logger.info(f"🆔 Signal ID: {signal_id_from_data}")
        logger.info(f"📡 Signal: {signal}")
        if is_catchup:
            logger.info(f"🔄 Caught up from MongoDB storage")
        logger.info("─" * 60)

        # Log to signal_processing.log (unified tracking)
        signal_env = signal_data.get('environment', 'production').upper()
        logger.info(f"SIGNAL: {signal_id_from_data} | RECEIVED | Strategy={strategy_name} | Instrument={signal.get('instrument') or signal.get('ticker')} | Action={signal.get('action')} | Environment={signal_env}")

        # Send Telegram notification
        try:
            from telegram.notifier import TelegramNotifier
            # Get environment from signal data, default to production
            signal_environment = signal_data.get('environment', 'production')
            notifier = TelegramNotifier(environment=signal_environment)
            notifier.notify_signal_received(signal_data)
        except Exception as e:
            logger.info(f"⚠️  Error sending Telegram notification: {e}")

        # MVP: Send signal to microservices via Pub/Sub
        if self.pubsub_publisher:
            try:
                self._publish_to_microservices(signal_data)
            except Exception as e:
                logger.info(f"⚠️  Error publishing to microservices: {e}")

        # Process signal through Mathematricks Trader (legacy)
        try:
            # Import here to avoid circular imports
            from src.execution.signal_processor import get_signal_processor

            processor = get_signal_processor()
            if processor:
                processor.process_new_signal(signal_data)
        except ImportError:
            # Signal processor not available (development mode)
            pass
        except Exception as e:
            logger.info(f"⚠️  Error processing signal in Mathematricks Trader: {e}")

    def _publish_to_microservices(self, signal_data: dict):
        """Publish signal to MVP microservices via Pub/Sub"""
        if not self.pubsub_publisher or not self.pubsub_topic_path:
            return

        # Generate clean signal ID: {strategy}_{YYYYMMDD_HHMMSS}_{seq}
        now = datetime.datetime.utcnow()
        strategy_name = signal_data.get('strategy_name', 'Unknown').replace(' ', '_').replace('-', '_')
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')

        # Extract just the sequence number from original signalID if available
        original_id = signal_data.get('signalID') or signal_data.get('signal_id')
        if original_id:
            # Extract sequence number from end of original ID (e.g., "001" from "SPY_20251027_104528_001")
            parts = str(original_id).split('_')
            if len(parts) > 0 and parts[-1].isdigit():
                seq = parts[-1].zfill(3)[:3]  # Ensure exactly 3 digits
            else:
                seq = str(int(now.microsecond / 1000)).zfill(3)[:3]
        else:
            # Use milliseconds as sequence number (always 3 digits)
            seq = str(int(now.microsecond / 1000)).zfill(3)[:3]

        signal_id = f"{strategy_name}_{date_str}_{time_str}_{seq}"

        # Convert to standardized format for Cerebro
        signal_payload = signal_data.get('signal', {})

        # Determine timestamp: use received_at, or signal_sent_EPOCH, or current time
        timestamp_value = signal_data.get('timestamp')
        if not timestamp_value:
            # Try received_at first
            if 'received_at' in signal_data and signal_data['received_at']:
                timestamp_value = signal_data['received_at'].isoformat() if isinstance(signal_data['received_at'], datetime.datetime) else signal_data['received_at']
            # Try signal_sent_EPOCH
            elif 'signal_sent_EPOCH' in signal_data and signal_data['signal_sent_EPOCH']:
                timestamp_value = datetime.datetime.fromtimestamp(signal_data['signal_sent_EPOCH']).isoformat()
            # Fallback to current time
            else:
                timestamp_value = datetime.datetime.utcnow().isoformat()

        standardized_signal = {
            "signal_id": signal_id,
            "strategy_id": signal_data.get('strategy_name', 'Unknown'),
            "timestamp": timestamp_value,
            "instrument": signal_payload.get('instrument') or signal_payload.get('ticker', ''),  # Support both 'instrument' and 'ticker' fields
            "direction": signal_payload.get('direction', 'LONG').upper(),  # Get direction from signal
            "action": signal_payload.get('action', 'ENTRY').upper(),
            "order_type": signal_payload.get('order_type', 'MARKET').upper(),
            "price": float(signal_payload.get('price', 0)),
            "quantity": float(signal_payload.get('quantity', 1)),
            "stop_loss": float(signal_payload.get('stop_loss', 0)),
            "take_profit": float(signal_payload.get('take_profit', 0)),
            "expiry": signal_payload.get('expiry'),  # For futures
            # Multi-asset support: preserve these fields from original signal
            "instrument_type": signal_payload.get('instrument_type'),  # STOCK, OPTION, FOREX, FUTURE
            "underlying": signal_payload.get('underlying'),  # For options
            "legs": signal_payload.get('legs'),  # For multi-leg options
            "exchange": signal_payload.get('exchange'),  # For futures
            "metadata": {
                "expected_alpha": 0.02,  # Would come from backtest data
                "original_signal": signal_data
            },
            "processed_by_cerebro": False,
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        # Publish to Pub/Sub
        message_data = json.dumps(standardized_signal).encode('utf-8')
        future = self.pubsub_publisher.publish(self.pubsub_topic_path, message_data)
        message_id = future.result(timeout=5.0)

        logger.info(f"\n🚀 Routing to MVP microservices (Cerebro → Execution)")
        logger.info(f"✅ Signal published to Cerebro: {message_id}")
        logger.info(f"   → Signal ID: {standardized_signal['signal_id']}")
        logger.info(f"   → Instrument: {standardized_signal['instrument']}")
        logger.info(f"   → Action: {standardized_signal['action']}")

    class SignalHandler(BaseHTTPRequestHandler):
        def __init__(self, collector, *args, **kwargs):
            self.collector = collector
            super().__init__(*args, **kwargs)

        def do_POST(self):
            received_time = datetime.datetime.now(datetime.timezone.utc)

            try:
                # Get content length and read data
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)

                # Parse JSON
                signal_data = json.loads(post_data.decode('utf-8'))

                # Check if this is a forwarded signal from Vercel
                if signal_data.get('source') == 'vercel_forwarded':
                    # Extract the original signal from the forwarded payload
                    original_signal = signal_data.get('original_signal', {})
                    forwarded_time = signal_data.get('forwarded_at')

                    logger.info(f"📡 Received forwarded signal via Cloudflare Tunnel")
                    if forwarded_time:
                        logger.info(f"🔄 Forwarded at: {forwarded_time}")

                    # Process the original signal
                    self.collector.process_signal(original_signal, received_time)
                else:
                    # Process direct signal
                    self.collector.process_signal(signal_data, received_time)

                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"status": "collected", "signal_id": len(self.collector.collected_signals)}
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                logger.info(f"❌ Error processing signal: {e}")
                self.send_response(400)
                self.end_headers()

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "Signal Collector Active",
                "signals_collected": len(self.collector.collected_signals),
                "webhook_url": self.collector.webhook_url
            }
            self.wfile.write(json.dumps(response).encode())

        def log_message(self, format, *args):
            # Suppress default HTTP server logs
            pass

    def start_local_server(self):
        """Start local server to receive signals for testing"""
        handler = lambda *args, **kwargs: self.SignalHandler(self, *args, **kwargs)
        self.server = HTTPServer(('localhost', self.local_port), handler)

        logger.info(f"🔧 Local signal collector server started on http://localhost:{self.local_port}")
        logger.info(f"💡 To test locally, send signals to: http://localhost:{self.local_port}")
        logger.info("─" * 60)

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            pass

    def monitor_signals(self):
        """Monitor signals using MongoDB Change Streams for real-time notifications"""
        logger.info("🔥 Press Ctrl+C to stop monitoring")
        logger.info("=" * 80)

        # PHASE 1: Catch-up mode - fetch any missed signals
        logger.info("\n🔄 PHASE 1: Catch-up Mode")
        if self.mongodb_collection is not None:
            self.fetch_missed_signals_from_mongodb()
        else:
            logger.info("❌ MongoDB connection failed - cannot start monitoring")
            logger.info("💡 Restart the collector to retry MongoDB connection")
            return

        # PHASE 2: Real-time mode - MongoDB Change Streams
        logger.info("\n📡 PHASE 2: Real-Time Mode - Change Streams")

        try:
            # Start Change Streams with retry logic
            self.start_change_stream_with_retry()

        except KeyboardInterrupt:
            logger.info("\n🛑 Signal monitoring stopped by user")
            self.display_summary()

    def display_summary(self):
        """Display summary of collected signals"""
        logger.info("\n" + "=" * 80)
        logger.info(f"📊 Mathematricks Capital Signal Collection Summary")
        logger.info(f"🌐 Webhook URL: {self.webhook_url}")
        logger.info(f"🔢 Total Signals Collected: {len(self.collected_signals)}")
        logger.info("=" * 80)

        if self.collected_signals:
            logger.info("📋 Signal Details:")
            for signal in self.collected_signals:
                logger.info(f"  #{signal['id']}: {signal['signal'].get('signal', {}).get('ticker', 'N/A')} "
                      f"{signal['signal'].get('signal', {}).get('action', 'N/A')} "
                      f"(Delay: {signal['delay_seconds']:.3f}s)")

            # Calculate average delay
            delays = [s['delay_seconds'] for s in self.collected_signals if s['delay_seconds'] > 0]
            if delays:
                avg_delay = sum(delays) / len(delays)
                logger.info(f"\n⚡ Average Delay: {avg_delay:.3f} seconds")
                logger.info(f"⚡ Min Delay: {min(delays):.3f} seconds")
                logger.info(f"⚡ Max Delay: {max(delays):.3f} seconds")

        logger.info("\n🎯 System Architecture:")
        logger.info("📡 TradingView → Vercel Webhook → MongoDB → Change Streams → Local Collector")
        logger.info("🔄 Catch-up: Fetch missed signals from MongoDB on startup")
        logger.info("⚡ Live: Real-time notifications via MongoDB Change Streams")

        logger.info("\n🧪 Test Commands:")
        logger.info("\n# Send signal using Python sender:")
        logger.info('python3 signal_sender.py --ticker AAPL --action BUY --price 150.25')
        logger.info('python3 signal_sender.py --test-suite')

        logger.info("\n# Test Production Webhook (will be stored in MongoDB):")
        logger.info(f'curl -X POST {self.webhook_url}/api/signals \\')
        logger.info('  -H "Content-Type: application/json" \\')
        logger.info('  -d \'{"passphrase": "yahoo123", "timestamp": "'+ datetime.datetime.now().isoformat() +'", "signal": {"ticker": "AAPL", "price": 150.25, "action": "BUY"}}\'')

        logger.info(f"\n# Test webhook status:")
        logger.info(f'curl -X GET {self.webhook_url}/api/signals')
        logger.info("=" * 80)

if __name__ == "__main__":
    import sys

    # Check for staging flag
    use_staging = "--staging" in sys.argv
    webhook_url = "https://staging.mathematricks.fund" if use_staging else "https://mathematricks.fund"

    env_name = "STAGING" if use_staging else "PRODUCTION"
    collector = WebhookSignalCollector(webhook_url)

    logger.info(f"🚀 Starting Mathematricks Fund Webhook Signal Collector ({env_name})")
    logger.info(f"🌐 Monitoring: {webhook_url}")
    logger.info("")

    collector.monitor_signals()