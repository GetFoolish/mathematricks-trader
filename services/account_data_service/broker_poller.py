"""
Background broker polling service
Polls all active trading accounts at regular intervals
Also watches MongoDB for position changes (event-driven polling)
"""
import threading
import time
import logging
from typing import Dict, Callable, Optional
import sys
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Add parent directory to path for broker imports
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '../../')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'services'))

from brokers import BrokerFactory
from account_data_service.repository import TradingAccountRepository
from exceptions import BrokerConnectionError

logger = logging.getLogger(__name__)


class MongoPositionWatcher:
    """
    Watches MongoDB trading_accounts collection for position changes
    Triggers immediate polling when open_positions array is updated
    """

    def __init__(self, mongodb_url: str, position_change_callback: Callable[[str], None]):
        """
        Initialize MongoDB position watcher

        Args:
            mongodb_url: MongoDB connection string
            position_change_callback: Function to call when positions change (receives account_id)
        """
        self.mongodb_url = mongodb_url
        self.position_change_callback = position_change_callback
        self.mongodb_client = None
        self.trading_accounts_collection = None
        self.resume_token = None
        self.running = False
        self.thread = None

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

            # Get trading_accounts collection
            db = self.mongodb_client['mathematricks_trading']
            self.trading_accounts_collection = db['trading_accounts']

            logger.info("✅ MongoPositionWatcher connected to MongoDB")
            return True
        except PyMongoError as e:
            logger.error(f"⚠️ MongoPositionWatcher connection failed: {e}")
            return False

    def start(self):
        """Start watching in background thread"""
        if self.running:
            logger.warning("MongoPositionWatcher already running")
            return

        if not self.connect():
            logger.error("❌ Failed to connect to MongoDB - position watching disabled")
            return

        self.running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        logger.info("✅ Started MongoDB position watching (event-driven polling)")

    def stop(self):
        """Stop watching gracefully"""
        logger.info("Stopping MongoDB position watcher...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)

        # Disconnect from MongoDB
        if self.mongodb_client:
            try:
                self.mongodb_client.close()
                logger.info("Disconnected from MongoDB")
            except Exception as e:
                logger.error(f"Error disconnecting from MongoDB: {e}")

    def _watch_loop(self):
        """Main watching loop (runs in background thread)"""
        while self.running:
            try:
                result = self._watch_for_position_changes()

                # Handle different return statuses
                if result == 'token_reset':
                    logger.info("🔄 Resume token reset - reconnecting immediately")
                    continue  # No backoff for token reset
                elif result == 'error':
                    logger.warning("⚠️ Watch error - retrying in 5 seconds...")
                    time.sleep(5)
                elif result == 'stopped':
                    break  # Graceful shutdown

            except Exception as e:
                logger.error(f"Unexpected error in watch loop: {e}", exc_info=True)
                time.sleep(5)

    def _watch_for_position_changes(self) -> str:
        """
        Watch for position changes using MongoDB Change Streams
        Returns: 'success', 'token_reset', 'error', or 'stopped'
        """
        if self.trading_accounts_collection is None:
            logger.error("❌ MongoDB not available - cannot watch for position changes")
            return 'error'

        try:
            # Build watch options with resume token if we have one
            watch_options = {}
            if self.resume_token:
                watch_options['resume_after'] = self.resume_token
                logger.debug("🔄 Resuming from previous position")

            # Pipeline to filter for updates to open_positions field
            pipeline = [
                {
                    '$match': {
                        'operationType': {'$in': ['update', 'replace']},
                        # Match when open_positions field is updated
                        '$or': [
                            {'updateDescription.updatedFields.open_positions': {'$exists': True}},
                            {'updateDescription.updatedFields': {'$regex': '^open_positions\\.'}}
                        ]
                    }
                }
            ]

            # Open change stream
            with self.trading_accounts_collection.watch(pipeline, full_document='updateLookup', **watch_options) as stream:
                logger.info("✅ Change Stream connected - watching for position updates...")

                for change in stream:
                    if not self.running:
                        return 'stopped'

                    try:
                        # Update resume token for reconnection resilience
                        self.resume_token = stream.resume_token

                        # Extract account_id from the changed document
                        document_key = change.get('documentKey', {})
                        full_document = change.get('fullDocument', {})
                        account_id = full_document.get('account_id')

                        if not account_id:
                            logger.warning("⚠️ Position change detected but no account_id found")
                            continue

                        # Log the position change detection
                        operation_type = change.get('operationType', 'unknown')
                        logger.info(f"🔔 Position change detected for {account_id} (operation: {operation_type})")

                        # Trigger callback to poll this account immediately
                        if self.position_change_callback:
                            try:
                                self.position_change_callback(account_id)
                            except Exception as e:
                                logger.error(f"Error in position change callback for {account_id}: {e}", exc_info=True)

                    except Exception as e:
                        logger.error(f"Error processing change event: {e}", exc_info=True)
                        continue

            return 'success'

        except PyMongoError as e:
            error_code = getattr(e, 'code', None)

            # Code 260 = Invalid resume token
            if error_code == 260:
                logger.warning("⚠️ Invalid resume token detected - resetting...")
                self.resume_token = None
                return 'token_reset'  # Retry immediately without backoff

            logger.error(f"❌ Change Stream error: {e}")
            return 'error'


class BrokerPoller:
    """Background service to poll broker accounts"""

    def __init__(self, repository: TradingAccountRepository, interval: int = 300, mongodb_url: Optional[str] = None):
        """
        Initialize broker poller

        Args:
            repository: TradingAccountRepository instance
            interval: Polling interval in seconds (default: 300 = 5 minutes)
            mongodb_url: MongoDB connection string for position watching (optional)
        """
        self.repository = repository
        self.interval = interval
        self.mongodb_url = mongodb_url
        self.running = False
        self.thread = None
        self.position_watcher = None
        self.broker_instances = {}  # Cache broker connections {account_id: broker}
        self.last_positions_state = {}  # Track last position state for change detection {account_id: positions_hash}
        self.poll_lock = threading.Lock()  # Prevent concurrent polling of same account

    def start(self):
        """Start polling in background thread"""
        if self.running:
            logger.warning("Poller already running")
            return

        self.running = True

        # Start scheduled polling thread
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f"✅ Started broker polling (interval: {self.interval}s)")

        # Start MongoDB position watcher (event-driven polling)
        if self.mongodb_url:
            try:
                self.position_watcher = MongoPositionWatcher(
                    mongodb_url=self.mongodb_url,
                    position_change_callback=self._on_position_change
                )
                self.position_watcher.start()
            except Exception as e:
                logger.error(f"Failed to start position watcher: {e}", exc_info=True)
                logger.warning("Continuing with scheduled polling only")
        else:
            logger.info("MongoDB URL not provided - position watching disabled")

    def stop(self):
        """Stop polling gracefully"""
        logger.info("Stopping broker poller...")
        self.running = False

        # Stop position watcher
        if self.position_watcher:
            self.position_watcher.stop()

        # Stop scheduled polling thread
        if self.thread:
            self.thread.join(timeout=10)

        # Disconnect all brokers
        for account_id, broker in self.broker_instances.items():
            try:
                broker.disconnect()
                logger.info(f"Disconnected broker for {account_id}")
            except Exception as e:
                logger.error(f"Error disconnecting {account_id}: {e}")

    def _poll_loop(self):
        """Main polling loop (runs in background thread)"""
        while self.running:
            try:
                self.poll_all_accounts()
            except Exception as e:
                logger.error(f"Polling error: {e}", exc_info=True)

            # Sleep in small intervals to allow quick shutdown
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

    def _on_position_change(self, account_id: str):
        """
        Callback triggered when MongoDB detects a position change
        Polls the specific account immediately (event-driven)

        Args:
            account_id: Account ID that had position change
        """
        logger.info(f"⚡ Event-driven poll triggered for {account_id}")

        # Get account document
        account = self.repository.get_account(account_id)
        if not account:
            logger.warning(f"Account {account_id} not found - skipping event-driven poll")
            return

        # For Mock broker, display MongoDB snapshot instead of polling
        # (polling would create circular loop since Mock reads from MongoDB)
        if account.get('broker') == 'Mock':
            self._display_mock_snapshot(account_id)
            return

        # Check if account is active
        if account.get('status') != 'ACTIVE':
            logger.debug(f"Account {account_id} not active - skipping event-driven poll")
            return

        # Use lock to prevent concurrent polling
        with self.poll_lock:
            try:
                self.poll_account(account, poll_type="EVENT-DRIVEN")
            except BrokerConnectionError as e:
                logger.warning(f"⚠️  {account_id} offline during event-driven poll: {e.message}")
                self.repository.update_connection_status(account_id, "DISCONNECTED", False)
            except Exception as e:
                logger.error(f"❌ Error in event-driven poll for {account_id}: {e}", exc_info=True)
                self.repository.update_connection_status(account_id, "ERROR", False)

    def _display_mock_snapshot(self, account_id: str):
        """
        Display current MongoDB positions for Mock broker without polling
        (ExecutionService is source of truth, we just read and display)
        """
        try:
            # Fetch account document directly from MongoDB
            account_doc = self.repository.get_account(account_id)
            if not account_doc:
                logger.warning(f"Account {account_id} not found for snapshot")
                return

            # Get positions and balances from MongoDB
            open_positions = account_doc.get('open_positions', [])
            # Filter for OPEN status
            open_positions = [p for p in open_positions if p.get('status') == 'OPEN']

            # Get balances
            equity = account_doc.get('balances', {}).get('equity', 1000000)
            cash = account_doc.get('balances', {}).get('cash_balance', 500000)

            # Display with clear formatting
            logger.info("-" * 50)
            logger.info(f"📸 EVENT-DRIVEN SNAPSHOT - {account_id}")
            logger.info(f"(ExecutionService is source of truth)")
            logger.info("-" * 50)
            logger.info(f"Equity: ${equity:,.2f} | Cash: ${cash:,.2f}")

            if len(open_positions) > 0:
                logger.info(f"Positions from MongoDB:")
                for pos in open_positions:
                    logger.info(
                        f"  • {pos.get('instrument')}: "
                        f"{pos.get('quantity', 0)} {pos.get('direction', 'LONG')} @ "
                        f"${pos.get('avg_entry_price', 0):.2f} | "
                        f"Status: {pos.get('status', 'UNKNOWN')}"
                    )
            else:
                logger.info("Positions: None")

            logger.info("-" * 50)

        except Exception as e:
            logger.error(f"Error displaying Mock snapshot for {account_id}: {e}", exc_info=True)

    def poll_all_accounts(self):
        """Poll all active accounts"""
        accounts = self.repository.list_accounts(status="ACTIVE")
        logger.info(f"📊 Polling {len(accounts)} active accounts...")

        for account in accounts:
            try:
                self.poll_account(account)
            except BrokerConnectionError as e:
                # Connection errors are expected when broker is offline - log as warning, not error
                account_id = account['account_id']
                logger.warning(f"⚠️  {account_id} offline: {e.message}")
                self.repository.update_connection_status(
                    account_id,
                    "DISCONNECTED",
                    False
                )
            except Exception as e:
                # Unexpected errors should be logged with traceback
                account_id = account['account_id']
                logger.error(f"❌ Error polling {account_id}: {e}", exc_info=True)
                self.repository.update_connection_status(
                    account_id,
                    "ERROR",
                    False
                )

    def poll_account(self, account: Dict, poll_type: str = "SCHEDULED"):
        """
        Poll single account for balances and positions

        Args:
            account: Account document from MongoDB
            poll_type: Type of poll - "SCHEDULED" or "EVENT-DRIVEN"
        """
        import asyncio

        account_id = account['account_id']
        auth = account['authentication_details']

        # Create broker config
        config = {
            "broker": account['broker'],
            "account_id": account_id,
        }

        # Add authentication details based on broker type
        if account['broker'] == "IBKR":
            config.update({
                "host": auth.get('host', '127.0.0.1'),
                "port": auth.get('port', 7497),
                "client_id": auth.get('client_id', 100)
            })
        elif account['broker'] == "Zerodha":
            config.update({
                "api_key": auth.get('api_key'),
                "api_secret": auth.get('api_secret'),
                "access_token": auth.get('access_token')
            })

        # For IBKR, we need to ensure we have an event loop
        # Run in a new thread if called from FastAPI context
        if account['broker'] == "IBKR":
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread - run in separate thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._poll_account_sync, account_id, config, auth)
                    try:
                        future.result(timeout=30)
                    except Exception as e:
                        # Re-raise to be caught by poll_all_accounts
                        raise e
                return

        # Get or create broker instance
        broker = self._get_broker(account_id, config)

        # Connect if needed
        if not broker.is_connected():
            logger.info(f"Connecting to {account_id}...")
            if not broker.connect():
                raise Exception("Failed to connect to broker")

        # Fetch balances
        balance = broker.get_account_balance()
        balances = {
            "base_currency": "USD",
            "equity": balance.get('equity', 0),
            "cash_balance": balance.get('cash_balance', 0),
            "margin_used": balance.get('margin_used', 0),
            "margin_available": balance.get('margin_available', 0),
            "unrealized_pnl": balance.get('unrealized_pnl', 0),
            "realized_pnl": balance.get('realized_pnl', 0),
            "margin_utilization_pct": self._calculate_margin_pct(balance)
        }
        self.repository.update_balances(account_id, balances)

        # Fetch positions
        positions = broker.get_open_positions()
        self.repository.update_broker_positions_snapshot(account_id, positions)

        # Update connection status
        self.repository.update_connection_status(account_id, "CONNECTED", True)

        # Check if positions changed
        positions_hash = self._hash_positions(positions)
        position_changed = (account_id not in self.last_positions_state or
                          self.last_positions_state[account_id] != positions_hash)
        self.last_positions_state[account_id] = positions_hash

        # Log detailed summary
        self._log_account_summary(account_id, balances, positions, position_changed, poll_type=poll_type)

    def _poll_account_sync(self, account_id: str, config: Dict, auth: Dict):
        """
        Synchronous version of poll_account for running in separate thread
        This creates its own event loop for IBKR
        """
        import asyncio

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create broker instance
            broker = BrokerFactory.create_broker(config)

            # Connect
            if not broker.is_connected():
                logger.info(f"Connecting to {account_id}...")
                if not broker.connect():
                    raise Exception("Failed to connect to broker")

            # Fetch balances
            balance = broker.get_account_balance()
            balances = {
                "base_currency": "USD",
                "equity": balance.get('equity', 0),
                "cash_balance": balance.get('cash_balance', 0),
                "margin_used": balance.get('margin_used', 0),
                "margin_available": balance.get('margin_available', 0),
                "unrealized_pnl": balance.get('unrealized_pnl', 0),
                "realized_pnl": balance.get('realized_pnl', 0),
                "margin_utilization_pct": self._calculate_margin_pct(balance)
            }
            self.repository.update_balances(account_id, balances)

            # Fetch positions
            positions = broker.get_open_positions()
            self.repository.update_positions(account_id, positions)

            # Update connection status
            self.repository.update_connection_status(account_id, "CONNECTED", True)

            # Check if positions changed
            positions_hash = self._hash_positions(positions)
            position_changed = (account_id not in self.last_positions_state or
                              self.last_positions_state[account_id] != positions_hash)
            self.last_positions_state[account_id] = positions_hash

            # Log detailed summary
            self._log_account_summary(account_id, balances, positions, position_changed, poll_type="SCHEDULED")

            # Disconnect
            broker.disconnect()

        finally:
            # Clean up event loop
            loop.close()

    def _get_broker(self, account_id: str, config: Dict):
        """
        Get or create broker instance

        Args:
            account_id: Account ID (for caching)
            config: Broker configuration

        Returns:
            Broker instance
        """
        if account_id not in self.broker_instances:
            logger.debug(f"Creating new broker instance for {account_id}")
            self.broker_instances[account_id] = BrokerFactory.create_broker(config)
        return self.broker_instances[account_id]

    @staticmethod
    def _calculate_margin_pct(balance: Dict) -> float:
        """
        Calculate margin utilization percentage

        Args:
            balance: Balance dict with equity and margin_used

        Returns:
            Margin utilization as percentage (0-100)
        """
        margin_used = balance.get('margin_used', 0)
        equity = balance.get('equity', 0)
        if equity > 0:
            return (margin_used / equity) * 100
        return 0.0

    @staticmethod
    def _hash_positions(positions: list) -> str:
        """
        Create hash of positions for change detection

        Args:
            positions: List of position dicts

        Returns:
            Hash string representing current positions state
        """
        import hashlib
        import json

        # Sort positions by instrument for consistent hashing
        sorted_positions = sorted(positions, key=lambda x: x.get('instrument', ''))

        # Create hash from relevant fields (instrument, quantity, side)
        position_data = [
            {
                'instrument': p.get('instrument'),
                'quantity': p.get('quantity'),
                'side': p.get('side'),
                'avg_price': p.get('avg_price')
            }
            for p in sorted_positions
        ]

        return hashlib.md5(json.dumps(position_data, sort_keys=True).encode()).hexdigest()

    def _log_account_summary(self, account_id: str, balances: Dict, positions: list, position_changed: bool, poll_type: str = "SCHEDULED"):
        """
        Log detailed account summary with clear visual separation

        Args:
            account_id: Account ID
            balances: Balance dict
            positions: List of positions
            position_changed: Whether positions changed since last poll
            poll_type: Type of poll - "SCHEDULED" or "EVENT-DRIVEN"
        """
        # Always display full account state with clear separator
        logger.info("-" * 50)
        logger.info(f"📊 {poll_type} POLL - {account_id}")
        logger.info("-" * 50)
        logger.info(f"Equity: ${balances['equity']:,.2f} | Cash: ${balances['cash_balance']:,.2f}")

        # Always show positions (not just when changed)
        if len(positions) > 0:
            logger.info(f"Positions:")
            for pos in positions:
                pnl = pos.get('unrealized_pnl', 0)
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                logger.info(
                    f"  • {pos.get('instrument')}: "
                    f"{pos.get('quantity')} {pos.get('side', 'LONG')} @ "
                    f"${pos.get('avg_price', 0):.2f} | "
                    f"PnL: {pnl_str}"
                )
        else:
            logger.info("Positions: None")

        logger.info("-" * 50)
