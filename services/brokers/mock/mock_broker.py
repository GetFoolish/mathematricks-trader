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
    - Returns mock account data
    - No external dependencies

    Example config:
    {
        "broker": "Mock",
        "account_id": "Mock_Paper",
        "initial_equity": 100000  # Optional, defaults to 100k
    }
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Mock broker with configuration"""
        super().__init__(config)

        self.broker_name = "Mock"
        self.account_id = config.get("account_id", "Mock_Paper")
        self.initial_equity = config.get("initial_equity", 1000000.0)

        # In-memory storage
        self.mock_orders = {}  # {broker_order_id: order_data}
        self.connected = False

        logger.info(f"Mock Broker initialized for account {self.account_id} (instant fills for testing)")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self) -> bool:
        """
        Establish mock connection (always succeeds instantly).

        Returns:
            True (always)
        """
        if self.connected:
            logger.info(f"Mock Broker: Already connected to {self.account_id}")
            return True

        self.connected = True
        logger.info(f"Mock Broker: Connected to {self.account_id} (no actual connection needed)")
        return True

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
        Return mock account balance.

        Args:
            account_id: Account ID (optional, uses self.account_id if not provided)

        Returns:
            Dict with equity, cash_balance, margin_used, etc.
        """
        account = account_id or self.account_id

        return {
            "account_id": account,
            "equity": self.initial_equity,
            "cash_balance": self.initial_equity * 0.5,  # 50% cash
            "margin_used": 0.0,
            "margin_available": self.initial_equity * 0.5,
            "buying_power": self.initial_equity * 2.0,  # 2x leverage
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
        Return mock margin information.

        Args:
            account_id: Account ID (optional)

        Returns:
            Dict with margin_used, margin_available, etc.
        """
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
