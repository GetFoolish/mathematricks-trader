#!/usr/bin/env python3
import json
import time
import datetime
from dateutil import parser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient
from pymongo.errors import PyMongoError

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

            print("✅ Connected to MongoDB Atlas")
            return True
        except PyMongoError as e:
            print(f"⚠️ MongoDB connection failed: {e}")
            print("📄 Will fall back to JSON file storage")
            return False

    def fetch_missed_signals_from_mongodb(self):
        """Fetch missed signals directly from MongoDB"""
        if self.mongodb_collection is None:
            print("❌ MongoDB not available - cannot fetch missed signals")
            return

        try:
            print("🔄 Checking for missed signals from MongoDB...")

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
                    print(f"⚠️ Invalid timestamp format: {self.last_signal_timestamp}")

            # Query MongoDB directly for unprocessed signals
            missed_signals_cursor = self.mongodb_collection.find(query_filter).sort('received_at', 1)
            missed_signals = list(missed_signals_cursor)

            if missed_signals:
                print(f"📥 Found {len(missed_signals)} missed signals in MongoDB")

                for signal_doc in missed_signals:
                    # Convert MongoDB document to our format
                    received_time = signal_doc['received_at']
                    if isinstance(received_time, str):
                        received_time = parser.parse(received_time)

                    # Reconstruct signal data from MongoDB format
                    signal_data = {
                        'timestamp': signal_doc.get('timestamp'),
                        'signal_id': signal_doc.get('signalID'),  # Fixed field name
                        'epoch_time': signal_doc.get('signal_sent_EPOCH'),  # Fixed field name
                        'signal': signal_doc.get('signal', {})  # Fixed: was 'signal_data', should be 'signal'
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

                print(f"✅ Successfully caught up with {len(missed_signals)} signals from MongoDB")
            else:
                print("✅ No missed signals found in MongoDB")

        except PyMongoError as e:
            print(f"❌ Error fetching from MongoDB: {e}")
            print("💡 Check MongoDB connection or restart collector")

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
            print("❌ MongoDB not available - cannot watch for new signals")
            return

        try:

            # Start watching with resume token if we have one
            watch_options = {}
            if self.resume_token:
                watch_options['resume_after'] = self.resume_token
                print(f"🔄 Resuming from previous position")

            # Determine which environment we're monitoring
            expected_environment = "staging" if "staging" in self.webhook_url else "production"

            # Open change stream (watch all operations - we only insert anyway)
            with self.mongodb_collection.watch([], **watch_options) as stream:
                print(f"✅ Change Stream connected - waiting for {expected_environment} signals only...")

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
                            print("⚠️ No document in change event")
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
                            'signal_id': new_document.get('signalID'),  # Fixed field name
                            'epoch_time': new_document.get('signal_sent_EPOCH'),  # Fixed field name
                            'signal': new_document.get('signal', {})  # Fixed: was 'signal_data', should be 'signal'
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
                        print(f"⚠️ Error processing change stream event: {e}")
                        continue

        except PyMongoError as e:
            print(f"❌ Change Stream error: {e}")
            print("🔄 Will retry connection...")
            return False
        except Exception as e:
            print(f"💥 Unexpected error in Change Stream: {e}")
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
                    print("🔄 Change Stream ended, restarting...")
                else:
                    # Connection failed, implement exponential backoff
                    retry_count += 1
                    delay = base_delay * (2 ** retry_count)
                    print(f"⏰ Retrying in {delay} seconds... (attempt {retry_count}/{max_retries})")
                    time.sleep(delay)

            except KeyboardInterrupt:
                print("\n🛑 Change Stream monitoring stopped by user")
                break
            except Exception as e:
                retry_count += 1
                delay = base_delay * (2 ** retry_count)
                print(f"💥 Unexpected error: {e}")
                print(f"⏰ Retrying in {delay} seconds... (attempt {retry_count}/{max_retries})")
                time.sleep(delay)

        if retry_count >= max_retries:
            print(f"❌ Failed to establish stable Change Stream after {max_retries} attempts")
            print("💡 Check MongoDB connection and restart collector")



    def calculate_delay(self, sent_timestamp: str, received_timestamp: datetime.datetime) -> float:
        """Calculate delay between sent and received timestamps"""
        try:
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
            print(f"⚠️ Error calculating delay: {e}")
            return 0.0

    def process_signal(self, signal_data: dict, received_time: datetime.datetime, is_catchup: bool = False, original_id: int = None):
        """Process and display received signal with timing information"""
        signal_id = original_id if is_catchup else len(self.collected_signals) + 1

        # Extract signal information
        timestamp = signal_data.get('timestamp', 'No timestamp')
        signal = signal_data.get('signal', {})

        # Get signal ID from the data
        signal_id_from_data = signal_data.get('signal_id') or signal_data.get('signalID')

        # Calculate delay if timestamp is provided
        delay = 0.0
        if timestamp != 'No timestamp':
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
        print(f"\n{signal_type}")
        if delay > 0:
            print(f"⚡ Delay: {delay:.3f} seconds")
        if signal_id_from_data:
            print(f"🆔 Signal ID: {signal_id_from_data}")
        print(f"📡 Signal: {signal}")
        if is_catchup:
            print(f"🔄 Caught up from MongoDB storage")
        print("─" * 60)

        # Process signal through Mathematricks Trader
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
            print(f"⚠️  Error processing signal in Mathematricks Trader: {e}")

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

                    print(f"📡 Received forwarded signal via Cloudflare Tunnel")
                    if forwarded_time:
                        print(f"🔄 Forwarded at: {forwarded_time}")

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
                print(f"❌ Error processing signal: {e}")
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

        print(f"🔧 Local signal collector server started on http://localhost:{self.local_port}")
        print(f"💡 To test locally, send signals to: http://localhost:{self.local_port}")
        print("─" * 60)

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            pass

    def monitor_signals(self):
        """Monitor signals using MongoDB Change Streams for real-time notifications"""
        print("🔥 Press Ctrl+C to stop monitoring")
        print("=" * 80)

        # PHASE 1: Catch-up mode - fetch any missed signals
        print("\n🔄 PHASE 1: Catch-up Mode")
        if self.mongodb_collection is not None:
            self.fetch_missed_signals_from_mongodb()
        else:
            print("❌ MongoDB connection failed - cannot start monitoring")
            print("💡 Restart the collector to retry MongoDB connection")
            return

        # PHASE 2: Real-time mode - MongoDB Change Streams
        print("\n📡 PHASE 2: Real-Time Mode - Change Streams")

        try:
            # Start Change Streams with retry logic
            self.start_change_stream_with_retry()

        except KeyboardInterrupt:
            print("\n🛑 Signal monitoring stopped by user")
            self.display_summary()

    def display_summary(self):
        """Display summary of collected signals"""
        print("\n" + "=" * 80)
        print(f"📊 Mathematricks Capital Signal Collection Summary")
        print(f"🌐 Webhook URL: {self.webhook_url}")
        print(f"🔢 Total Signals Collected: {len(self.collected_signals)}")
        print("=" * 80)

        if self.collected_signals:
            print("📋 Signal Details:")
            for signal in self.collected_signals:
                print(f"  #{signal['id']}: {signal['signal'].get('signal', {}).get('ticker', 'N/A')} "
                      f"{signal['signal'].get('signal', {}).get('action', 'N/A')} "
                      f"(Delay: {signal['delay_seconds']:.3f}s)")

            # Calculate average delay
            delays = [s['delay_seconds'] for s in self.collected_signals if s['delay_seconds'] > 0]
            if delays:
                avg_delay = sum(delays) / len(delays)
                print(f"\n⚡ Average Delay: {avg_delay:.3f} seconds")
                print(f"⚡ Min Delay: {min(delays):.3f} seconds")
                print(f"⚡ Max Delay: {max(delays):.3f} seconds")

        print("\n🎯 System Architecture:")
        print("📡 TradingView → Vercel Webhook → MongoDB → Change Streams → Local Collector")
        print("🔄 Catch-up: Fetch missed signals from MongoDB on startup")
        print("⚡ Live: Real-time notifications via MongoDB Change Streams")

        print("\n🧪 Test Commands:")
        print("\n# Send signal using Python sender:")
        print('python3 signal_sender.py --ticker AAPL --action BUY --price 150.25')
        print('python3 signal_sender.py --test-suite')

        print("\n# Test Production Webhook (will be stored in MongoDB):")
        print(f'curl -X POST {self.webhook_url}/api/signals \\')
        print('  -H "Content-Type: application/json" \\')
        print('  -d \'{"passphrase": "yahoo123", "timestamp": "'+ datetime.datetime.now().isoformat() +'", "signal": {"ticker": "AAPL", "price": 150.25, "action": "BUY"}}\'')

        print(f"\n# Test webhook status:")
        print(f'curl -X GET {self.webhook_url}/api/signals')
        print("=" * 80)

if __name__ == "__main__":
    import sys

    # Check for staging flag
    use_staging = "--staging" in sys.argv
    webhook_url = "https://staging.mathematricks.fund" if use_staging else "https://mathematricks.fund"

    env_name = "STAGING" if use_staging else "PRODUCTION"
    collector = WebhookSignalCollector(webhook_url)

    print(f"🚀 Starting Mathematricks Fund Webhook Signal Collector ({env_name})")
    print(f"🌐 Monitoring: {webhook_url}")
    print()

    collector.monitor_signals()