"""
Background broker polling service
Polls all active trading accounts at regular intervals
"""
import threading
import time
import logging
from typing import Dict
import sys
import os

# Add parent directory to path for broker imports
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '../../')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'services'))

from brokers import BrokerFactory
from account_data_service.repository import TradingAccountRepository

logger = logging.getLogger(__name__)


class BrokerPoller:
    """Background service to poll broker accounts"""

    def __init__(self, repository: TradingAccountRepository, interval: int = 300):
        """
        Initialize broker poller

        Args:
            repository: TradingAccountRepository instance
            interval: Polling interval in seconds (default: 300 = 5 minutes)
        """
        self.repository = repository
        self.interval = interval
        self.running = False
        self.thread = None
        self.broker_instances = {}  # Cache broker connections {account_id: broker}

    def start(self):
        """Start polling in background thread"""
        if self.running:
            logger.warning("Poller already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f"✅ Started broker polling (interval: {self.interval}s)")

    def stop(self):
        """Stop polling gracefully"""
        logger.info("Stopping broker poller...")
        self.running = False
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

    def poll_all_accounts(self):
        """Poll all active accounts"""
        accounts = self.repository.list_accounts(status="ACTIVE")
        logger.info(f"📊 Polling {len(accounts)} active accounts...")

        for account in accounts:
            try:
                self.poll_account(account)
            except Exception as e:
                account_id = account['account_id']
                logger.error(f"❌ Error polling {account_id}: {e}", exc_info=True)
                self.repository.update_connection_status(
                    account_id,
                    "ERROR",
                    False
                )

    def poll_account(self, account: Dict):
        """
        Poll single account for balances and positions

        Args:
            account: Account document from MongoDB
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
        self.repository.update_positions(account_id, positions)

        # Update connection status
        self.repository.update_connection_status(account_id, "CONNECTED", True)

        logger.info(f"✅ Polled {account_id}: Equity=${balances['equity']:,.2f}, {len(positions)} positions")

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

            logger.info(f"✅ Polled {account_id}: Equity=${balances['equity']:,.2f}, {len(positions)} positions")

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
