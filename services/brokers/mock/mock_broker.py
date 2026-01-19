"""
Mock Broker Implementation
Provides instant fills for testing when markets are closed or for development
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import random
import time
import uuid
from pymongo import MongoClient

# Import base classes and exceptions
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base import AbstractBroker, OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)

# MongoDB connection will be lazy-loaded
_mongo_client = None
_trading_accounts_collection = None


def get_trading_accounts_collection():
    """Lazy load MongoDB connection for position tracking"""
    global _mongo_client, _trading_accounts_collection

    if _trading_accounts_collection is None:
        try:
            # Use MONGODB_URI (same as other services)
            MONGO_URI = os.getenv('MONGODB_URI')
            if not MONGO_URI:
                logger.warning("MONGODB_URI not set, position tracking disabled")
                return None

            _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            db = _mongo_client['mathematricks_trading']
            _trading_accounts_collection = db['trading_accounts']
            logger.info("✅ Connected to MongoDB for position tracking")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return None

    return _trading_accounts_collection


class MockBroker(AbstractBroker):
    """
    Mock broker for testing without real market connection.

    Features:
    - Instant order fills (no waiting for market data)
    - Supports all instrument types (stocks, forex, options, futures, commodities)
    - Supports MARKET and LIMIT orders
    - Uses MongoDB as single source of truth for account data
    - No cached values - all balances read from database

    Architecture:
    - Account balances are stored in MongoDB trading_accounts collection
    - get_account_balance() reads from MongoDB, not cached values
    - get_margin_info() reads from MongoDB, not cached values
    - get_open_positions() reads from MongoDB, not cached values
    - This ensures consistency after clear_test_data.py resets

    Example config:
    {
        "broker": "Mock",
        "account_id": "Mock_Paper",
        "initial_equity": 100000  # Used only for initial account creation
    }
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Mock broker with configuration"""
        super().__init__(config)

        self.broker_name = "Mock"
        self.account_id = config.get("account_id", "Mock_Paper")
        self.initial_equity = config.get("initial_equity", 1000000.0)
        
        # Read-only mode: prevents MongoDB config overwrites when used as secondary broker in BrokerModeAdapter
        self.read_only = config.get("read_only", False)

        # In-memory storage
        self.mock_orders = {}  # {broker_order_id: order_data}
        self.connected = False

        if self.read_only:
            logger.info(f"Mock Broker initialized for account {self.account_id} (read-only mode - no MongoDB writes)")
        else:
            logger.info(f"Mock Broker initialized for account {self.account_id} (instant fills for testing)")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self) -> bool:
        """
        Establish mock connection (always succeeds instantly).
        Also ensures the account exists in trading_accounts collection with proper schema.

        Returns:
            True (always)
        """
        if self.connected:
            logger.info(f"Mock Broker: Already connected to {self.account_id}")
            return True

        # Ensure account exists in database with complete schema
        self._ensure_account_exists()

        self.connected = True
        logger.info(f"Mock Broker: Connected to {self.account_id} (no actual connection needed)")
        return True

    def _ensure_account_exists(self):
        """
        Ensure Mock account exists in trading_accounts collection with proper schema.
        Replaces existing account to ensure fresh state on each connection.
        Skips in read_only mode (when used as secondary broker in BrokerModeAdapter).
        
        CRITICAL: Only updates balances/positions, NEVER overwrites broker/mode/auth_details
        to prevent corrupting IBKR accounts that are temporarily using Mock broker.
        """
        # Skip if read_only - this Mock broker is secondary in a hybrid setup
        if self.read_only:
            logger.debug(f"Mock broker in read-only mode - skipping account creation for {self.account_id}")
            return
            
        trading_accounts = get_trading_accounts_collection()
        
        # Check if account already exists
        existing_account = trading_accounts.find_one({"account_id": self.account_id})
        
        if existing_account:
            # Account exists - ONLY update balances and positions, never broker/mode/auth
            logger.debug(f"Mock broker: Account {self.account_id} exists - updating balances only (preserving broker config)")
            trading_accounts.update_one(
                {"account_id": self.account_id},
                {"$set": {
                    "balances.equity": self.initial_equity,
                    "balances.cash": self.initial_equity / 2,
                    "balances.cash_balance": self.initial_equity / 2,
                    "balances.margin_used": 0.0,
                    "balances.margin_available": self.initial_equity / 2,
                    "balances.buying_power": self.initial_equity * 2,
                    "balances.unrealized_pnl": 0.0,
                    "balances.realized_pnl": 0.0,
                    "balances.last_updated": datetime.utcnow(),
                    "open_positions": [],
                    "updated_at": datetime.utcnow()
                }}
            )
            logger.debug(f"   Updated balances: Equity=${self.initial_equity:,.2f}, Buying Power=${self.initial_equity * 2:,.2f}")
            return
        
        # Account doesn't exist - create it (only for pure Mock accounts)
        logger.debug(f"Mock broker: Creating new account {self.account_id}")
        if trading_accounts is None:
            logger.warning("Cannot create account document - MongoDB not available")
            return

        mock_account = {
            "account_id": self.account_id,
            "account_name": f"{self.account_id} Mock Paper Trading",
            "broker": "Mock",
            "account_number": f"MOCK_{self.account_id}",
            "account_type": "Paper",
            "authentication_details": {
                "auth_type": "MOCK",
                "initial_equity": self.initial_equity
            },
            "balances": {
                "equity": self.initial_equity,
                "cash": self.initial_equity / 2.0,
                "cash_balance": self.initial_equity / 2.0,
                "margin_used": 0.0,
                "margin_available": self.initial_equity / 2.0,
                "buying_power": self.initial_equity * 2.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "last_updated": datetime.utcnow()
            },
            "open_positions": [],
            "status": "ACTIVE",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        try:
            # Insert only if doesn't exist (this path should only run for new Mock-only accounts)
            trading_accounts.insert_one(mock_account)
            logger.info(f"✅ Created fresh {self.account_id} Mock account")
            logger.info(f"   Initial Equity: ${mock_account['balances']['equity']:,.2f}")
            logger.info(f"   Buying Power: ${mock_account['balances']['buying_power']:,.2f}")

        except Exception as e:
            if 'duplicate key' in str(e).lower():
                # Race condition - account was created by another process
                logger.debug(f"Account {self.account_id} already exists (race condition)")
            else:
                logger.error(f"Failed to create Mock account: {e}")

    def disconnect(self) -> bool:
        """
        Close mock connection.

        Returns:
            True (always)
        """
        if self.connected:
            self.connected = False
            logger.info(f"Mock Broker: Disconnected from {self.account_id}")
        return True

    def is_connected(self) -> bool:
        """
        Check if mock broker is connected.

        Returns:
            True if connected, False otherwise
        """
        return self.connected

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place mock order - instant fill.

        Args:
            order: Order dictionary with instrument, quantity, order_type, etc.

        Returns:
            Dict with broker_order_id, status='Filled', avg_fill_price, etc.
        """
        # Generate mock broker order ID
        broker_order_id = f"MOCK_{int(time.time())}_{random.randint(1000, 9999)}"

        # Determine fill price based on order type
        order_type = order.get('order_type', 'MARKET')
        quantity = order.get('quantity', 0)

        if order_type == 'LIMIT':
            # Use limit price for LIMIT orders
            fill_price = order.get('limit_price', 100.0)
        else:
            # MARKET order - use simple mock price
            # In a more sophisticated version, could use actual market data
            fill_price = order.get('price', 100.0)  # Use suggested price if available

        # Store order in memory
        self.mock_orders[broker_order_id] = {
            **order,
            'broker_order_id': broker_order_id,
            'fill_price': fill_price,
            'filled_quantity': quantity,
            'remaining_quantity': 0,
            'status': 'Filled',
            'timestamp': datetime.utcnow()
        }

        logger.debug(
            f"Mock Broker: Order {broker_order_id} FILLED instantly | "
            f"Instrument={order.get('instrument')} | "
            f"Qty={quantity} | "
            f"Price=${fill_price:.2f}"
        )

        # Return fill confirmation
        return {
            "broker_order_id": broker_order_id,
            "status": "Filled",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Mock order filled instantly",
            "filled": quantity,
            "remaining": 0,
            "avg_fill_price": fill_price,
            "fills": [
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "quantity": quantity,
                    "price": fill_price,
                    "exchange": "MOCK",
                    "execution_id": str(uuid.uuid4())
                }
            ]
        }

    def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel mock order (always succeeds).

        Args:
            broker_order_id: Mock order ID to cancel

        Returns:
            True (always, even if order doesn't exist)
        """
        logger.info(f"Mock Broker: Cancelled order {broker_order_id}")

        if broker_order_id in self.mock_orders:
            self.mock_orders[broker_order_id]['status'] = 'Cancelled'

        return True

    def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """
        Get mock order status.

        Args:
            broker_order_id: Mock order ID

        Returns:
            Dict with status, filled_quantity, remaining_quantity, fills, etc.

        Raises:
            ValueError: If order not found
        """
        if broker_order_id not in self.mock_orders:
            logger.warning(f"Mock Broker: Order {broker_order_id} not found")
            raise ValueError(f"Order {broker_order_id} not found in mock broker")

        order = self.mock_orders[broker_order_id]

        return {
            "broker_order_id": broker_order_id,
            "status": order['status'],
            "filled_quantity": order.get('filled_quantity', 0),
            "remaining_quantity": order.get('remaining_quantity', 0),
            "avg_fill_price": order['fill_price'],
            "timestamp": order['timestamp'].isoformat() + "Z",
            "fills": [
                {
                    "timestamp": order['timestamp'].isoformat() + "Z",
                    "quantity": order.get('filled_quantity', 0),
                    "price": order['fill_price'],
                    "exchange": "MOCK",
                    "execution_id": str(uuid.uuid4())
                }
            ]
        }

    # ========================================================================
    # ACCOUNT DATA
    # ========================================================================

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return account balance from MongoDB (single source of truth).

        Args:
            account_id: Account ID (optional, uses self.account_id if not provided)

        Returns:
            Dict with equity, cash_balance, margin_used, etc.
        """
        account = account_id or self.account_id

        try:
            # Get MongoDB collection (lazy-loaded)
            trading_accounts_collection = get_trading_accounts_collection()
            if trading_accounts_collection is None:
                logger.warning("MongoDB not available, returning fallback balances")
                # Fallback only if MongoDB is unavailable
                return {
                    "account_id": account,
                    "equity": self.initial_equity,
                    "cash_balance": self.initial_equity * 0.5,
                    "margin_used": 0.0,
                    "margin_available": self.initial_equity * 0.5,
                    "buying_power": self.initial_equity * 2.0,
                    "unrealized_pnl": 0.0,
                    "realized_pnl": 0.0,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

            # Fetch account document from MongoDB
            account_doc = trading_accounts_collection.find_one({"account_id": account})

            if not account_doc or 'balances' not in account_doc:
                logger.warning(f"Account {account} not found in MongoDB, returning fallback balances")
                # Fallback only if account doesn't exist yet
                return {
                    "account_id": account,
                    "equity": self.initial_equity,
                    "cash_balance": self.initial_equity * 0.5,
                    "margin_used": 0.0,
                    "margin_available": self.initial_equity * 0.5,
                    "buying_power": self.initial_equity * 2.0,
                    "unrealized_pnl": 0.0,
                    "realized_pnl": 0.0,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

            # Return balances from MongoDB (single source of truth)
            balances = account_doc['balances']
            return {
                "account_id": account,
                "equity": balances.get('equity', 0.0),
                "cash_balance": balances.get('cash_balance', 0.0),
                "margin_used": balances.get('margin_used', 0.0),
                "margin_available": balances.get('margin_available', 0.0),
                "buying_power": balances.get('buying_power', 0.0),
                "unrealized_pnl": balances.get('unrealized_pnl', 0.0),
                "realized_pnl": balances.get('realized_pnl', 0.0),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except Exception as e:
            logger.error(f"Error fetching account balance from MongoDB: {e}", exc_info=True)
            # Fallback on error
            return {
                "account_id": account,
                "equity": self.initial_equity,
                "cash_balance": self.initial_equity * 0.5,
                "margin_used": 0.0,
                "margin_available": self.initial_equity * 0.5,
                "buying_power": self.initial_equity * 2.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return open positions from MongoDB trading_accounts collection.

        Args:
            account_id: Account ID (optional, defaults to self.account_id)

        Returns:
            List of open position dicts with OPEN status
        """
        try:
            acc_id = account_id or self.account_id

            # Get MongoDB collection (lazy-loaded)
            trading_accounts_collection = get_trading_accounts_collection()
            if trading_accounts_collection is None:
                logger.warning("MongoDB not available, returning empty positions")
                return []

            # Fetch account document from MongoDB
            account_doc = trading_accounts_collection.find_one({"account_id": acc_id})

            if not account_doc:
                return []

            # Get open_positions array and filter for OPEN status only
            all_positions = account_doc.get('open_positions', [])
            open_positions = [pos for pos in all_positions if pos.get('status') == 'OPEN']

            # Convert to format expected by AccountDataService
            formatted_positions = []
            for pos in open_positions:
                formatted_positions.append({
                    'instrument': pos.get('instrument'),
                    'quantity': pos.get('quantity', 0),
                    'side': pos.get('direction', 'LONG'),
                    'avg_price': pos.get('avg_entry_price', 0),
                    'current_price': pos.get('current_price', pos.get('avg_entry_price', 0)),
                    'unrealized_pnl': pos.get('unrealized_pnl', 0),
                    'strategy_id': pos.get('strategy_id')
                })

            return formatted_positions

        except Exception as e:
            logger.error(f"Error fetching positions from MongoDB: {e}", exc_info=True)
            return []

    def get_margin_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return margin information from MongoDB (single source of truth).

        Args:
            account_id: Account ID (optional)

        Returns:
            Dict with margin_used, margin_available, etc.
        """
        account = account_id or self.account_id

        try:
            # Get MongoDB collection (lazy-loaded)
            trading_accounts_collection = get_trading_accounts_collection()
            if trading_accounts_collection is None:
                logger.warning("MongoDB not available, returning fallback margin info")
                # Fallback only if MongoDB is unavailable
                return {
                    "margin_used": 0.0,
                    "margin_available": self.initial_equity * 0.5,
                    "margin_requirement": 0.0,
                    "excess_liquidity": self.initial_equity * 0.5,
                    "leverage": 2.0,
                    "margin_utilization_pct": 0.0,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

            # Fetch account document from MongoDB
            account_doc = trading_accounts_collection.find_one({"account_id": account})

            if not account_doc or 'balances' not in account_doc:
                logger.warning(f"Account {account} not found in MongoDB, returning fallback margin info")
                # Fallback only if account doesn't exist yet
                return {
                    "margin_used": 0.0,
                    "margin_available": self.initial_equity * 0.5,
                    "margin_requirement": 0.0,
                    "excess_liquidity": self.initial_equity * 0.5,
                    "leverage": 2.0,
                    "margin_utilization_pct": 0.0,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

            # Calculate from MongoDB balances (single source of truth)
            balances = account_doc['balances']
            margin_used = balances.get('margin_used', 0.0)
            margin_available = balances.get('margin_available', 0.0)
            equity = balances.get('equity', 0.0)

            # Calculate margin utilization percentage
            margin_utilization_pct = 0.0
            if equity > 0:
                margin_utilization_pct = (margin_used / equity) * 100.0

            return {
                "margin_used": margin_used,
                "margin_available": margin_available,
                "margin_requirement": margin_used,  # For mock, requirement = used
                "excess_liquidity": margin_available,
                "leverage": 2.0,  # Mock broker uses 2x leverage
                "margin_utilization_pct": margin_utilization_pct,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except Exception as e:
            logger.error(f"Error fetching margin info from MongoDB: {e}", exc_info=True)
            # Fallback on error
            return {
                "margin_used": 0.0,
                "margin_available": self.initial_equity * 0.5,
                "margin_requirement": 0.0,
                "excess_liquidity": self.initial_equity * 0.5,
                "leverage": 2.0,
                "margin_utilization_pct": 0.0,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

    def get_open_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return open orders (empty, since all orders fill instantly).

        Args:
            account_id: Account ID (optional)

        Returns:
            Empty list (all orders fill instantly)
        """
        return []

    # ========================================================================
    # MARKET DATA (Optional - for future use)
    # ========================================================================

    def get_market_price(self, symbol: str, instrument_type: str = "STOCK") -> float:
        """
        Return mock market price.

        Args:
            symbol: Instrument symbol
            instrument_type: Type of instrument

        Returns:
            Mock price (100.0 for simplicity)
        """
        # Simple mock price - could be enhanced to return realistic prices
        return 100.0

    def get_ticker_price(self, symbol: str, signal_price: Optional[float] = None) -> float:
        """
        Get ticker price for margin calculation and order execution.
        
        For Mock broker: Returns signal's intended price for testing purposes.
        This allows testing the full signal flow with realistic prices.
        Real brokers (like IBKR) fetch actual market data and ignore signal_price.
        
        Args:
            symbol: Instrument symbol
            signal_price: Intended price from signal (for testing)
        
        Returns:
            Price to use (signal_price if provided, otherwise 100.0 default)
        """
        if signal_price is not None and signal_price > 0:
            logger.debug(f"Mock Broker: Using signal price ${signal_price:.2f} for {symbol}")
            return signal_price
        
        # Fallback: Return default mock price
        logger.debug(f"Mock Broker: No signal price provided, using default $100.00 for {symbol}")
        return 100.0

    # ========================================================================
    # QUANTITY PRECISION
    # ========================================================================

    def get_quantity_precision(self, symbol: str, instrument_type: str) -> int:
        """
        Get the number of decimal places allowed for quantity.

        Mock broker uses predefined precision by instrument type.

        Args:
            symbol: Asset symbol (e.g., "AAPL", "EURUSD")
            instrument_type: Type of instrument

        Returns:
            int: Number of decimal places (0 for integers)
        """
        precision_map = {
            'STOCK': 0,      # Integer shares
            'ETF': 0,        # Integer shares
            'OPTION': 0,     # Integer contracts
            'FUTURE': 0,     # Integer contracts
            'FOREX': 0,      # Units (whole units for mock)
            'CRYPTO': 8,     # Up to 8 decimal places for crypto
        }

        precision = precision_map.get(instrument_type.upper(), 0)
        logger.debug(f"Mock Broker: Precision for {symbol} ({instrument_type}): {precision} decimals")
        return precision
