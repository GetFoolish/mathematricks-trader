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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('signal_ingestion')

# Setup signal processing log (unified log for signal journey)
signal_processing_handler = logging.FileHandler(os.path.join(PROJECT_ROOT, 'logs', 'signal_processing.log'))
signal_processing_handler.setLevel(logging.INFO)
signal_processing_formatter = logging.Formatter(
    '%(asctime)s | [COLLECTOR] | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
signal_processing_handler.setFormatter(signal_processing_formatter)
signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage())
logger.addHandler(signal_processing_handler)


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

    def process_signal(self, signal_data: dict, received_time: datetime.datetime, is_catchup: bool = False, original_id: int = None):
        """Process and route received signal"""
        signal_id = original_id if is_catchup else len(self.collected_signals) + 1

        # Extract signal information
        timestamp = signal_data.get('timestamp', 'No timestamp')
        signal = signal_data.get('signal', {})
        strategy_name = signal_data.get('strategy_name', 'Unknown Strategy')

        # Get signal ID from the data
        signal_id_from_data = signal_data.get('signal_id') or signal_data.get('signalID')

        # Calculate delay
        delay = 0.0
        if timestamp and timestamp != 'No timestamp':
            delay = self.calculate_delay(timestamp, received_time)

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
        if delay > 0:
            logger.info(f"⚡ Delay: {delay:.3f} seconds")
        if signal_id_from_data:
            logger.info(f"🆔 Signal ID: {signal_id_from_data}")
        logger.info(f"📡 Signal: {signal}")
        if is_catchup:
            logger.info("🔄 Caught up from MongoDB storage")
        logger.info("─" * 60)

        # Log to signal_processing.log (unified tracking)
        signal_env = signal_data.get('environment', 'production').upper()
        logger.info(
            f"SIGNAL: {signal_id_from_data} | RECEIVED | Strategy={strategy_name} | "
            f"Instrument={signal.get('instrument') or signal.get('ticker')} | "
            f"Action={signal.get('action')} | Environment={signal_env}"
        )

        # Send Telegram notification
        try:
            from telegram.notifier import TelegramNotifier
            signal_environment = signal_data.get('environment', 'production')
            notifier = TelegramNotifier(environment=signal_environment)
            notifier.notify_signal_received(signal_data)
        except Exception as e:
            logger.warning(f"⚠️ Error sending Telegram notification: {e}")

        # Publish to microservices via Pub/Sub
        if self.pubsub_publisher:
            try:
                self.publish_to_pubsub(signal_data)
            except Exception as e:
                logger.error(f"⚠️ Error publishing to microservices: {e}")

    def publish_to_pubsub(self, signal_data: dict):
        """Publish signal to MVP microservices via Pub/Sub"""
        if not self.pubsub_publisher or not self.pubsub_topic_path:
            return

        # Standardize signal format
        standardized_signal = SignalStandardizer.standardize(signal_data)

        # Publish to Pub/Sub
        message_data = SignalStandardizer.to_json(standardized_signal)
        future = self.pubsub_publisher.publish(self.pubsub_topic_path, message_data)
        message_id = future.result(timeout=5.0)

        logger.info("\n🚀 Routing to MVP microservices (Cerebro → Execution)")
        logger.info(f"✅ Signal published to Cerebro: {message_id}")
        logger.info(f"   → Signal ID: {standardized_signal['signal_id']}")
        logger.info(f"   → Instrument: {standardized_signal['instrument']}")
        logger.info(f"   → Action: {standardized_signal['action']}")

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
