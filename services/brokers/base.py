"""
Base Broker Interface
All broker integrations must implement this interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum


class OrderSide(Enum):
    """Order side (buy/sell)"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class AbstractBroker(ABC):
    """
    Base class for all broker integrations.

    All brokers must implement this interface to be compatible with:
    - ExecutionService (order placement)
    - AccountDataService (account data retrieval)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize broker with configuration.

        Args:
            config: Broker-specific configuration
                Example for IBKR:
                {
                    "broker": "IBKR",
                    "host": "127.0.0.1",
                    "port": 7497,
                    "client_id": 1,
                    "account_id": "DU123456"
                }

                Example for Zerodha:
                {
                    "broker": "Zerodha",
                    "api_key": "xxx",
                    "api_secret": "yyy",
                    "access_token": "zzz",
                    "user_id": "AB1234"
                }
        """
        self.config = config
        self.broker_name = config.get("broker", "Unknown")
        self.account_id = config.get("account_id") or config.get("user_id")

    # CONNECTION MANAGEMENT

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to broker.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close connection to broker.

        Returns:
            True if disconnection successful
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to broker.

        Returns:
            True if connected, False otherwise
        """
        pass

    # ORDER MANAGEMENT (for ExecutionService)

    @abstractmethod
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place an order with the broker.

        This method accepts orders in the INTERNAL STANDARD FORMAT used across
        the Mathematricks trading system. Each broker implementation is responsible
        for translating this format to its broker-specific schema.

        INTERNAL STANDARD ORDER SCHEMA (what ExecutionService sends):
        {
            'order_id': str,              # Internal tracking ID (not sent to broker)
            'strategy_id': str,           # Strategy identifier (not sent to broker)
            'instrument': str,            # Universal symbol (e.g., "AAPL", "AUDCAD")
            'instrument_type': str,       # "STOCK" | "ETF" | "OPTION" | "FOREX" | "FUTURE" | "CRYPTO"
            'direction': str,             # "LONG" | "SHORT" (universal direction)
            'action': str,                # "ENTRY" | "EXIT" | "SCALE_IN" | "SCALE_OUT" (not sent to broker)
            'quantity': float,            # Quantity (can be fractional for forex/crypto)
            'order_type': str,            # "MARKET" | "LIMIT" | "STOP" | "STOP_LIMIT"
            'limit_price': float,         # Optional: for LIMIT orders
            'stop_price': float,          # Optional: for STOP orders

            # For multi-leg (options)
            'legs': [                     # Optional: array of legs for complex orders
                {
                    'strike': float,
                    'expiry': str,        # Format: "YYYYMMDD"
                    'right': str,         # "C" | "P" | "CALL" | "PUT"
                    'action': str,        # "BUY" | "SELL"
                    'quantity': int
                }
            ],

            # Additional optional fields
            'underlying': str,            # For options/futures
            'expiry': str,                # For futures/options
            'exchange': str,              # Exchange code (can be inferred by broker)
            'account_id': str             # Optional account identifier
        }

        BROKER IMPLEMENTATION REQUIREMENTS:
        - Each broker MUST implement a `_translate_order()` method that converts
          the internal format to broker-specific format
        - Translation should happen at the START of place_order()
        - Common translations needed:
          * 'instrument' → broker's symbol field name (e.g., 'symbol', 'tradingsymbol')
          * 'direction' → broker's side field (LONG→BUY, SHORT→SELL)
          * 'quantity' → may need type conversion (float → int)
          * Add broker-specific fields (exchange, product type, variety, etc.)

        Args:
            order: Order details in INTERNAL STANDARD FORMAT (see above)

        Returns:
            {
                "broker_order_id": "12345",
                "status": "SUBMITTED" | "PENDING" | "REJECTED",
                "timestamp": "2025-01-07T12:00:00Z",
                "message": "Order submitted successfully"
            }

        Raises:
            BrokerConnectionError: If not connected to broker
            OrderRejectedError: If broker rejects the order
            BrokerAPIError: For other broker API errors
        """
        pass

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            broker_order_id: Broker's order ID

        Returns:
            True if cancellation successful

        Raises:
            OrderNotFoundError: If order doesn't exist
            BrokerAPIError: For API errors
        """
        pass

    @abstractmethod
    def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """
        Get current status and fill details of an order.

        Args:
            broker_order_id: Broker's order ID

        Returns:
            {
                "broker_order_id": "12345",
                "status": "FILLED" | "PARTIALLY_FILLED" | "SUBMITTED" | "CANCELLED",
                "filled_quantity": 100,
                "remaining_quantity": 0,
                "avg_fill_price": 150.25,
                "fills": [
                    {
                        "timestamp": "2025-01-07T12:00:01Z",
                        "quantity": 50,
                        "price": 150.20
                    },
                    {
                        "timestamp": "2025-01-07T12:00:02Z",
                        "quantity": 50,
                        "price": 150.30
                    }
                ]
            }

        Raises:
            OrderNotFoundError: If order doesn't exist
        """
        pass

    # ACCOUNT DATA (for AccountDataService)

    @abstractmethod
    def get_account_balance(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get account balance and equity.

        Args:
            account_id: Optional account ID (uses default from config if not provided)

        Returns:
            {
                "account_id": "IBKR_Main",
                "equity": 250000.00,
                "cash_balance": 50000.00,
                "margin_used": 100000.00,
                "margin_available": 150000.00,
                "buying_power": 200000.00,
                "timestamp": "2025-01-07T12:00:00Z"
            }
        """
        pass

    @abstractmethod
    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Args:
            account_id: Optional account ID

        Returns:
            [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "side": "LONG" | "SHORT",
                    "avg_price": 150.00,
                    "current_price": 152.00,
                    "unrealized_pnl": 200.00,
                    "realized_pnl": 0.00,
                    "market_value": 15200.00
                }
            ]
        """
        pass

    @abstractmethod
    def get_margin_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed margin information.

        Args:
            account_id: Optional account ID

        Returns:
            {
                "margin_used": 100000.00,
                "margin_available": 150000.00,
                "margin_requirement": 100000.00,
                "excess_liquidity": 150000.00,
                "leverage": 2.0,
                "margin_utilization_pct": 40.0
            }
        """
        pass

    @abstractmethod
    def get_open_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open (unfilled) orders.

        Args:
            account_id: Optional account ID

        Returns:
            [
                {
                    "broker_order_id": "12345",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": 100,
                    "order_type": "LIMIT",
                    "limit_price": 150.00,
                    "status": "SUBMITTED",
                    "timestamp": "2025-01-07T12:00:00Z"
                }
            ]
        """
        pass

    # UTILITY METHODS

    def get_broker_name(self) -> str:
        """Get broker name"""
        return self.broker_name

    def get_account_id(self) -> str:
        """Get default account ID"""
        return self.account_id
