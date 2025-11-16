#!/usr/bin/env python3
"""
SignalIngestionService
Monitors MongoDB for new trading signals and routes them to microservices via Pub/Sub
"""

import os
import sys
import logging
import threading
import datetime
from dateutil import parser
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Load environment variables
load_dotenv()

# Add project root to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from services.signal_ingestion.mongodb_watcher import MongoDBWatcher
from services.signal_ingestion.signal_standardizer import SignalStandardizer

# Try to import Pub/Sub for MVP microservices bridge
try:
    from google.cloud import pubsub_v1
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False

# Setup logging
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'signal_ingestion.log')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Create custom formatter matching Cerebro format
custom_formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')

# Create file handler with custom format
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(custom_formatter)

# Create console handler with same format
console_handler = logging.StreamHandler()
console_handler.setFormatter(custom_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger('signal_ingestion')

# Signal processing handler - unified log for signal journey (lazy initialization)
signal_processing_handler = None

def get_signal_processing_logger():
    """Lazy initialization of signal_processing.log handler"""
    global signal_processing_handler
    if signal_processing_handler is None:
        signal_processing_handler = logging.FileHandler(os.path.join(PROJECT_ROOT, 'logs', 'signal_processing.log'))
        signal_processing_handler.setLevel(logging.INFO)
        signal_processing_formatter = logging.Formatter(
            '%(asctime)s | [COLLECTOR] | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        signal_processing_handler.setFormatter(signal_processing_formatter)
        signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage())
        logger.addHandler(signal_processing_handler)
        logger.info("Signal processing log initialized")
    return logger


class SignalIngestionService:
    """
    Main service class for signal ingestion
    Watches MongoDB and publishes to Pub/Sub
    """

    def __init__(self, environment: str = 'production'):
        self.environment = environment
        self.collected_signals = []

        # MongoDB configuration
        mongodb_url = os.getenv('MONGODB_URI')
        if not mongodb_url:
            logger.error("MONGODB_URI not set in environment")
            sys.exit(1)

        # Initialize MongoDB watcher
        self.watcher = MongoDBWatcher(mongodb_url, environment)
        self.watcher.set_signal_callback(self.process_signal)

        # Connect to signal_store collection
        try:
            # Only use TLS for remote MongoDB Atlas connections
            use_tls = 'mongodb+srv' in mongodb_url or 'mongodb.net' in mongodb_url
            if use_tls:
                self.mongo_client = MongoClient(mongodb_url, tls=True, tlsAllowInvalidCertificates=True)
            else:
                self.mongo_client = MongoClient(mongodb_url)
            db = self.mongo_client['mathematricks_trading']
            self.signal_store_collection = db['signal_store']
            logger.info("✅ Connected to signal_store collection")
        except PyMongoError as e:
            logger.error(f"⚠️ Failed to connect to signal_store: {e}")
            self.signal_store_collection = None

        # Initialize Pub/Sub publisher
        self.pubsub_publisher = None
        self.pubsub_topic_path = None
        if PUBSUB_AVAILABLE:
            try:
                project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
                self.pubsub_publisher = pubsub_v1.PublisherClient()
                self.pubsub_topic_path = self.pubsub_publisher.topic_path(project_id, 'standardized-signals')
                logger.info("✅ Pub/Sub bridge enabled - signals will route to microservices")
            except Exception as e:
                logger.warning(f"⚠️ Pub/Sub initialization failed: {e}")
                self.pubsub_publisher = None

        logger.info("=" * 80)
        logger.info(f"SignalIngestionService Starting ({environment.upper()})")
        logger.info("=" * 80)

    def calculate_delay(self, sent_timestamp: str, received_timestamp: datetime.datetime) -> float:
        """Calculate delay between sent and received timestamps"""
        try:
            if not sent_timestamp or sent_timestamp == 'No timestamp':
                return 0.0

            sent_dt = parser.parse(sent_timestamp)

            # Make both timestamps timezone-aware
            if sent_dt.tzinfo is None:
                sent_dt = sent_dt.replace(tzinfo=datetime.timezone.utc)
            if received_timestamp.tzinfo is None:
                received_timestamp = received_timestamp.replace(tzinfo=datetime.timezone.utc)

            delay_seconds = (received_timestamp - sent_dt).total_seconds()
            return delay_seconds
        except Exception as e:
            logger.warning(f"⚠️ Error calculating delay: {e}")
            return 0.0

    def save_to_signal_store(self, signal_id: str, mongodb_object_id, signal_data: dict,
                            received_time: datetime.datetime, sent_timestamp: str,
                            receive_lag_ms: float) -> str:
        """
        Save signal receipt metadata to signal_store collection
        Returns: signal_store document ID (for Cerebro to update later)
        """
        if self.signal_store_collection is None:
            logger.warning("⚠️ signal_store not available - skipping storage")
            return None

        try:
            # Parse sent timestamp
            sent_dt = None
            if sent_timestamp:
                try:
                    sent_dt = parser.parse(sent_timestamp)
                    if sent_dt.tzinfo is None:
                        sent_dt = sent_dt.replace(tzinfo=datetime.timezone.utc)
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse sent_timestamp: {e}")

            # Create signal_store document
            signal_store_doc = {
                "signal_id": signal_id,
                "mongodb_object_id": mongodb_object_id,
                "received_at": received_time,
                "signal_sent_timestamp": sent_dt,
                "receive_lag_ms": int(receive_lag_ms * 1000) if receive_lag_ms else 0,
                "environment": self.environment,
                "signal_data": signal_data,
                "cerebro_decision": None,  # Will be updated by Cerebro
                "order_id": None,          # Will be updated by Execution Service
                "processing_complete": False,
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            }

            # Insert into MongoDB
            result = self.signal_store_collection.insert_one(signal_store_doc)
            signal_store_id = str(result.inserted_id)

            logger.info(f"💾 Saved to signal_store: {signal_store_id}")
            return signal_store_id

        except PyMongoError as e:
            logger.error(f"⚠️ Error saving to signal_store: {e}")
            return None

    def process_signal(self, signal_data: dict, received_time: datetime.datetime, is_catchup: bool = False, mongodb_object_id = None):
        """Process and route received signal"""
        signal_id = mongodb_object_id if is_catchup else len(self.collected_signals) + 1

        # Extract signal information
        timestamp = signal_data.get('timestamp')
        # Fall back to signal_sent_EPOCH if timestamp not provided
        if not timestamp and signal_data.get('signal_sent_EPOCH'):
            timestamp = datetime.datetime.fromtimestamp(signal_data['signal_sent_EPOCH'], tz=datetime.timezone.utc).isoformat()

        signal = signal_data.get('signal', {})
        strategy_name = signal_data.get('strategy_name', 'Unknown Strategy')

        # Get signal ID from the data
        signal_id_from_data = signal_data.get('signal_id') or signal_data.get('signalID')

        # Calculate delay
        delay = 0.0
        if timestamp:
            delay = self.calculate_delay(timestamp, received_time)

        # Get mathematricks_signal_id from signal_data (created by mongodb_watcher)
        mathematricks_signal_id = signal_data.get('mathematricks_signal_id')
        if not mathematricks_signal_id:
            logger.warning("⚠️ No mathematricks_signal_id in signal_data - signal may not be processed correctly")
        else:
            logger.info(f"🔗 Using signal_store document: {mathematricks_signal_id}")

        # Store signal in memory
        signal_record = {
            'id': signal_id,
            'received_time': received_time,
            'sent_timestamp': timestamp,
            'delay_seconds': delay,
            'signal': signal_data,
            'is_catchup': is_catchup
        }
        self.collected_signals.append(signal_record)

        # Display signal information
        signal_type = "📥 CATCHUP" if is_catchup else "🔥 REAL-TIME SIGNAL DETECTED!"
        logger.info(f"\n{signal_type}")
        logger.info(f"📊 Strategy: {strategy_name}")
        if signal_id_from_data:
            logger.info(f"🆔 Signal ID: {signal_id_from_data}")
        if delay > 0:
            sent_dt_str = parser.parse(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'Unknown'
            recd_dt_str = received_time.strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"⚡ Lag: {delay:.3f}s [Sent: {sent_dt_str}, Recd: {recd_dt_str}]")

        # Format signal details dynamically
        if isinstance(signal, list):
            # Multi-leg signal
            logger.info("📋 Signal Details (Multi-leg):")
            for i, leg in enumerate(signal, 1):
                logger.info(f"  Leg {i}:")
                for key, value in leg.items():
                    if value is not None and value != '':
                        logger.info(f"    • {key}: {value}")
        else:
            # Single-leg signal
            logger.info("📋 Signal Details:")
            for key, value in signal.items():
                if value is not None and value != '':
                    logger.info(f"  • {key}: {value}")

        if is_catchup:
            logger.info("🔄 Caught up from MongoDB storage")

        # Initialize signal processing logger on first signal
        signal_logger = get_signal_processing_logger()

        # Log to signal_processing.log (unified tracking)
        signal_env = signal_data.get('environment', 'production').upper()

        # Handle signal as array (new format) or dict (legacy)
        signal_for_log = signal[0] if isinstance(signal, list) else signal

        signal_logger.info(
            f"SIGNAL: {signal_id_from_data} | RECEIVED | Strategy={strategy_name} | "
            f"Instrument={signal_for_log.get('instrument') or signal_for_log.get('ticker')} | "
            f"Action={signal_for_log.get('action')} | Environment={signal_env}"
        )

        # Send Telegram notification
        try:
            from telegram.notifier import TelegramNotifier
            signal_environment = signal_data.get('environment', 'production')
            notifier = TelegramNotifier(environment=signal_environment)
            notifier.notify_signal_received(signal_data, lag_seconds=delay, sent_timestamp=timestamp, received_timestamp=received_time)
        except Exception as e:
            logger.warning(f"⚠️ Error sending Telegram notification: {e}")

        # Publish to microservices via Pub/Sub
        if self.pubsub_publisher:
            try:
                self.publish_to_pubsub(signal_data, mathematricks_signal_id)
            except Exception as e:
                logger.error(f"⚠️ Error publishing to microservices: {e}")

    def publish_to_pubsub(self, signal_data: dict, mathematricks_signal_id: str = None):
        """Publish signal to MVP microservices via Pub/Sub"""
        if not self.pubsub_publisher or not self.pubsub_topic_path:
            return

        # Standardize signal format
        standardized_signal = SignalStandardizer.standardize(signal_data)

        # Add mathematricks_signal_id for Cerebro to update
        if mathematricks_signal_id:
            standardized_signal['mathematricks_signal_id'] = mathematricks_signal_id

        # Publish to Pub/Sub
        message_data = SignalStandardizer.to_json(standardized_signal)
        future = self.pubsub_publisher.publish(self.pubsub_topic_path, message_data)
        message_id = future.result(timeout=5.0)

        logger.info("\n🚀 Routing to MVP microservices (Cerebro → Execution)")
        logger.info(f"✅ Signal published to Cerebro: {message_id}")
        logger.info(f"   → Signal ID: {standardized_signal['signal_id']}")
        logger.info(f"   → Mathematricks Signal ID: {mathematricks_signal_id}")
        logger.info(f"   → Instrument: {standardized_signal['instrument']}")
        logger.info(f"   → Action: {standardized_signal['action']}")
        logger.info("-" * 50)

    def start(self):
        """Start the signal ingestion service"""
        webhook_url = "staging.mathematricks.fund" if self.environment == "staging" else "mathematricks.fund"
        logger.info(f"🚀 Starting Signal Ingestion Service ({self.environment.upper()})")
        logger.info(f"🌐 Monitoring: {webhook_url}")
        logger.info("")

        # Start MongoDB watcher in background thread
        watcher_thread = threading.Thread(target=self.watcher.start_with_retry, daemon=True)
        watcher_thread.start()

        # Keep main thread alive
        try:
            watcher_thread.join()
        except KeyboardInterrupt:
            logger.info("\n🛑 Signal Ingestion Service stopped by user")
            self.display_summary()

    def display_summary(self):
        """Display summary of collected signals"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 Signal Collection Summary")
        logger.info(f"🔢 Total Signals Collected: {len(self.collected_signals)}")
        logger.info("=" * 80)

        if self.collected_signals:
            logger.info("📋 Signal Details:")
            for signal in self.collected_signals:
                logger.info(
                    f"  #{signal['id']}: {signal['signal'].get('signal', {}).get('ticker', 'N/A')} "
                    f"{signal['signal'].get('signal', {}).get('action', 'N/A')} "
                    f"(Delay: {signal['delay_seconds']:.3f}s)"
                )

            # Calculate average delay
            delays = [s['delay_seconds'] for s in self.collected_signals if s['delay_seconds'] > 0]
            if delays:
                avg_delay = sum(delays) / len(delays)
                logger.info(f"\n⚡ Average Delay: {avg_delay:.3f} seconds")
                logger.info(f"⚡ Min Delay: {min(delays):.3f} seconds")
                logger.info(f"⚡ Max Delay: {max(delays):.3f} seconds")

        logger.info("=" * 80)


if __name__ == "__main__":
    # Check for staging flag
    use_staging = "--staging" in sys.argv
    environment = "staging" if use_staging else "production"

    # Create and start service
    service = SignalIngestionService(environment=environment)
    service.start()
