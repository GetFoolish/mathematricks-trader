"""
Zerodha (Kite Connect) Broker Implementation
Uses Kite Connect API for order management and account data
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    logging.warning("kiteconnect not installed - Zerodha broker will not be functional")

# Import base classes and exceptions
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base import AbstractBroker, OrderSide, OrderType, OrderStatus
from exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    OrderNotFoundError,
    BrokerAPIError,
    InsufficientFundsError,
    InvalidSymbolError,
    AuthenticationError,
    MarketClosedError
)

logger = logging.getLogger(__name__)


class ZerodhaBroker(AbstractBroker):
    """
    Zerodha broker implementation using Kite Connect API.

    Example config:
    {
        "broker": "Zerodha",
        "api_key": "your_api_key",
        "api_secret": "your_api_secret",
        "access_token": "your_access_token",
        "user_id": "AB1234"
    }

    Note: Zerodha requires manual login flow to get access_token.
    See: https://kite.trade/docs/connect/v3/user/
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Zerodha broker with configuration"""
        super().__init__(config)

        if not KITE_AVAILABLE:
            raise ImportError(
                "kiteconnect library not installed. Install with: pip install kiteconnect"
            )

        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.access_token = config.get("access_token")

        if not self.api_key:
            raise ValueError("api_key required for Zerodha broker")

        # Initialize Kite Connect client
        self.kite = KiteConnect(api_key=self.api_key)

        # Set access token if provided
        if self.access_token:
            self.kite.set_access_token(self.access_token)

        # Track orders for status queries
        self.active_orders = {}  # {order_id: kite_order_id}

        logger.info(f"Initialized Zerodha broker for user: {self.account_id}")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self) -> bool:
        """
        Verify connection to Zerodha (validate access token).

        For Zerodha, connection is established by validating the access token.
        Unlike IBKR, there's no persistent connection - each API call is stateless.

        Returns:
            True if connection successful (access token valid)

        Raises:
            BrokerConnectionError: If access token is invalid
            AuthenticationError: If authentication fails
        """
        try:
            if not self.access_token:
                raise AuthenticationError(
                    "No access_token provided. Zerodha requires manual login flow.",
                    broker_name="Zerodha",
                    auth_method="ACCESS_TOKEN"
                )

            # Validate access token by fetching profile
            profile = self.kite.profile()
            logger.info(f"✅ Connected to Zerodha as: {profile.get('user_name')} ({profile.get('email')})")
            return True

        except Exception as e:
            error_msg = f"Failed to connect to Zerodha: {str(e)}"
            logger.error(error_msg)
            if "token" in str(e).lower() or "session" in str(e).lower():
                raise AuthenticationError(error_msg, broker_name="Zerodha", auth_method="ACCESS_TOKEN")
            else:
                raise BrokerConnectionError(error_msg, broker_name="Zerodha")

    def disconnect(self) -> bool:
        """
        Close connection to Zerodha.

        For Zerodha, there's no persistent connection to close.
        This method is a no-op for API compatibility.

        Returns:
            True
        """
        logger.info("Zerodha disconnect called (no-op for REST API)")
        return True

    def is_connected(self) -> bool:
        """
        Check if currently connected to Zerodha (has valid access token).

        Returns:
            True if access token exists, False otherwise
        """
        return self.access_token is not None

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    def _translate_direction_to_side(self, direction: str) -> str:
        """
        Translate internal direction to Zerodha side.

        Args:
            direction: Internal direction ("LONG" or "SHORT")

        Returns:
            Zerodha side ("BUY" or "SELL")
        """
        mapping = {
            'LONG': 'BUY',
            'SHORT': 'SELL'
        }
        direction_upper = direction.upper() if direction else ''
        return mapping.get(direction_upper, direction_upper)

    def _determine_exchange(self, order: Dict[str, Any]) -> str:
        """
        Determine appropriate exchange for Zerodha order.

        Args:
            order: Internal order format

        Returns:
            Exchange code (NSE, BSE, NFO, MCX, etc.)
        """
        # If exchange explicitly provided, use it
        if 'exchange' in order:
            return order['exchange'].upper()

        # Otherwise infer from instrument_type
        instrument_type = order.get('instrument_type', 'STOCK').upper()

        if instrument_type in ['STOCK', 'ETF']:
            return 'NSE'  # Default equity exchange
        elif instrument_type in ['OPTION', 'FUTURE']:
            return 'NFO'  # National Futures & Options exchange
        elif instrument_type == 'FOREX':
            return 'CDS'  # Currency Derivatives Segment
        else:
            return 'NSE'  # Safe default

    def _determine_product_type(self, order: Dict[str, Any]) -> str:
        """
        Determine Zerodha product type based on order characteristics.

        Product types:
        - CNC (Cash and Carry): Delivery trading for stocks
        - MIS (Margin Intraday Square-off): Intraday with leverage
        - NRML (Normal): Futures and Options, overnight positions

        Args:
            order: Internal order format

        Returns:
            Product type (CNC, MIS, NRML)
        """
        # If product explicitly provided, use it
        if 'product' in order:
            return order['product'].upper()

        instrument_type = order.get('instrument_type', 'STOCK').upper()

        # F&O always use NRML
        if instrument_type in ['OPTION', 'FUTURE']:
            return 'NRML'

        # For stocks/ETFs, default to CNC (delivery)
        # Users can override this in their signals if they want intraday (MIS)
        return 'CNC'

    def _translate_order(self, internal_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate internal order schema to Zerodha-specific schema.

        This method converts the universal internal order format to Zerodha's
        Kite Connect API format.

        Internal Schema (what ExecutionService sends):
        {
            'order_id': str,
            'strategy_id': str,
            'instrument': str,         # Universal symbol
            'instrument_type': str,    # "STOCK" | "OPTION" | "FOREX" | "FUTURE"
            'direction': str,          # "LONG" | "SHORT"
            'quantity': float,
            'order_type': str,         # "MARKET" | "LIMIT"
            'limit_price': float       # Optional
        }

        Zerodha Schema (what Kite API expects):
        {
            'tradingsymbol': str,      # Zerodha's symbol format
            'side': str,               # "BUY" | "SELL"
            'quantity': int,
            'order_type': str,
            'exchange': str,           # "NSE" | "BSE" | "NFO" | "CDS"
            'product': str,            # "CNC" | "MIS" | "NRML"
            'variety': str             # "regular" | "amo" | "co" | "iceberg"
        }

        Args:
            internal_order: Standard internal order format

        Returns:
            Zerodha-formatted order data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        logger.debug(f"Translating internal order to Zerodha format: {internal_order.get('order_id', 'unknown')}")

        # Field translations
        zerodha_order = {
            # Rename 'instrument' to 'symbol' (Zerodha uses 'tradingsymbol' but we'll use 'symbol' for now)
            'symbol': internal_order.get('instrument', '').upper(),

            # Translate 'direction' to 'side' (LONG→BUY, SHORT→SELL)
            'side': self._translate_direction_to_side(internal_order.get('direction', '')),

            # Convert quantity to integer
            'quantity': int(internal_order.get('quantity', 0)),

            # Pass-through
            'order_type': internal_order.get('order_type', 'MARKET'),

            # Zerodha-specific fields (determined from context)
            'exchange': self._determine_exchange(internal_order),
            'product': self._determine_product_type(internal_order),
            'variety': internal_order.get('variety', 'regular').lower()
        }

        # Conditional fields
        if 'limit_price' in internal_order and internal_order['limit_price']:
            zerodha_order['limit_price'] = internal_order['limit_price']

        if 'stop_price' in internal_order and internal_order['stop_price']:
            zerodha_order['trigger_price'] = internal_order['stop_price']  # Zerodha calls it trigger_price

        logger.debug(f"Translated order - symbol: {zerodha_order.get('symbol')}, side: {zerodha_order.get('side')}, exchange: {zerodha_order.get('exchange')}, product: {zerodha_order.get('product')}")
        return zerodha_order

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place an order with Zerodha.

        This method accepts orders in the internal standard format and automatically
        translates them to Zerodha-specific format before placement.

        Args:
            order: Order details in internal standard format
                {
                    "instrument": "RELIANCE",              # Universal symbol
                    "direction": "LONG" | "SHORT",        # Internal direction
                    "quantity": 100,                      # Can be float
                    "order_type": "MARKET" | "LIMIT",
                    "limit_price": 2500.00,               # for LIMIT orders
                    "instrument_type": "STOCK" | "OPTION" | "FUTURE" | "FOREX",
                    "exchange": "NSE",                    # Optional, inferred if not provided
                    "product": "CNC",                     # Optional, inferred if not provided
                    "variety": "regular"                  # Optional
                }

        Returns:
            {
                "broker_order_id": "210101000000123",
                "status": "SUBMITTED" | "PENDING" | "REJECTED",
                "timestamp": "2025-01-07T12:00:00Z",
                "message": "Order submitted successfully"
            }

        Raises:
            BrokerConnectionError: If not connected
            OrderRejectedError: If broker rejects the order
            InvalidSymbolError: If symbol is invalid
            BrokerAPIError: For other broker API errors
        """
        try:
            # Ensure connected
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to Zerodha - access token missing", broker_name="Zerodha")

            # Step 1: Translate internal order format to Zerodha format
            order = self._translate_order(order)
            logger.info(f"Order translated for Zerodha: {order.get('symbol')} {order.get('side')} {order.get('quantity')} @ {order.get('exchange')}")

            # Step 2: Validate required fields (now in Zerodha format)
            symbol = order.get("symbol", "").upper().strip()
            side = order.get("side", "").upper()
            quantity = order.get("quantity", 0)
            order_type = order.get("order_type", "MARKET").upper()

            if not symbol:
                raise ValueError("Missing required field: 'symbol'")

            if side not in ["BUY", "SELL"]:
                raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")

            if quantity <= 0:
                raise ValueError(f"Invalid quantity: {quantity}. Must be > 0")

            # Map to Zerodha parameters
            exchange = order.get("exchange", "NSE").upper()
            product = order.get("product", "CNC").upper()  # CNC = delivery
            variety = order.get("variety", "regular").lower()

            # Determine transaction type
            transaction_type = self.kite.TRANSACTION_TYPE_BUY if side == "BUY" else self.kite.TRANSACTION_TYPE_SELL

            # Prepare order parameters
            order_params = {
                "tradingsymbol": symbol,
                "exchange": exchange,
                "transaction_type": transaction_type,
                "quantity": int(quantity),
                "product": product,
                "variety": variety
            }

            # Add order type specific parameters
            if order_type == "MARKET":
                order_params["order_type"] = self.kite.ORDER_TYPE_MARKET
            elif order_type == "LIMIT":
                limit_price = order.get("limit_price")
                if not limit_price:
                    raise ValueError("limit_price required for LIMIT orders")
                order_params["order_type"] = self.kite.ORDER_TYPE_LIMIT
                order_params["price"] = float(limit_price)
            else:
                # Default to market
                order_params["order_type"] = self.kite.ORDER_TYPE_MARKET

            logger.info(f"📤 Placing Zerodha order: {side} {quantity} {symbol} @ {exchange}")

            # Place order
            try:
                order_id = self.kite.place_order(**order_params)
                logger.info(f"✅ Order placed successfully: {order_id}")

                # Store order ID for tracking
                self.active_orders[str(order_id)] = order_id

                return {
                    "broker_order_id": str(order_id),
                    "status": "SUBMITTED",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "message": "Order submitted successfully"
                }

            except Exception as kite_error:
                error_str = str(kite_error)

                # Check for specific error types
                if "margins" in error_str.lower() or "funds" in error_str.lower():
                    raise InsufficientFundsError(
                        f"Insufficient funds: {error_str}",
                        broker_name="Zerodha"
                    )
                elif "invalid" in error_str.lower() and "symbol" in error_str.lower():
                    raise InvalidSymbolError(
                        f"Invalid symbol: {error_str}",
                        broker_name="Zerodha",
                        symbol=symbol
                    )
                elif "market" in error_str.lower() and "closed" in error_str.lower():
                    raise MarketClosedError(
                        f"Market closed: {error_str}",
                        broker_name="Zerodha",
                        symbol=symbol
                    )
                else:
                    raise OrderRejectedError(
                        f"Order rejected: {error_str}",
                        broker_name="Zerodha",
                        rejection_reason=error_str
                    )

        except (BrokerConnectionError, OrderRejectedError, InvalidSymbolError, InsufficientFundsError, MarketClosedError):
            raise
        except ValueError as ve:
            raise OrderRejectedError(str(ve), broker_name="Zerodha")
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to place order: {str(e)}", broker_name="Zerodha")

    def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            broker_order_id: Zerodha's order ID

        Returns:
            True if cancellation successful

        Raises:
            OrderNotFoundError: If order doesn't exist
            BrokerAPIError: For API errors
        """
        try:
            logger.info(f"🚫 Cancelling Zerodha order: {broker_order_id}")

            # Cancel order
            try:
                self.kite.cancel_order(
                    variety=self.kite.VARIETY_REGULAR,
                    order_id=broker_order_id
                )

                # Remove from tracking
                if broker_order_id in self.active_orders:
                    del self.active_orders[broker_order_id]

                logger.info(f"✅ Order {broker_order_id} cancelled")
                return True

            except Exception as kite_error:
                error_str = str(kite_error)

                if "not found" in error_str.lower() or "invalid" in error_str.lower():
                    raise OrderNotFoundError(
                        f"Order not found: {error_str}",
                        broker_name="Zerodha",
                        broker_order_id=broker_order_id
                    )
                else:
                    raise BrokerAPIError(
                        f"Failed to cancel order: {error_str}",
                        broker_name="Zerodha"
                    )

        except OrderNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error cancelling order {broker_order_id}: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to cancel order: {str(e)}", broker_name="Zerodha")

    def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """
        Get current status and fill details of an order.

        Args:
            broker_order_id: Zerodha's order ID

        Returns:
            {
                "broker_order_id": "210101000000123",
                "status": "FILLED" | "PARTIALLY_FILLED" | "SUBMITTED" | "CANCELLED",
                "filled_quantity": 100,
                "remaining_quantity": 0,
                "avg_fill_price": 2500.25,
                "fills": [...]
            }

        Raises:
            OrderNotFoundError: If order doesn't exist
        """
        try:
            # Get order history (includes all statuses/fills)
            try:
                order_history = self.kite.order_history(order_id=broker_order_id)

                if not order_history:
                    raise OrderNotFoundError(
                        f"Order {broker_order_id} not found",
                        broker_name="Zerodha",
                        broker_order_id=broker_order_id
                    )

                # Get latest status (last entry in history)
                latest = order_history[-1]

                # Map Zerodha status to our standard status
                kite_status = latest.get("status", "").upper()
                if kite_status == "COMPLETE":
                    status = "FILLED"
                elif latest.get("filled_quantity", 0) > 0:
                    status = "PARTIALLY_FILLED"
                elif kite_status == "CANCELLED":
                    status = "CANCELLED"
                elif kite_status == "REJECTED":
                    status = "REJECTED"
                else:
                    status = "SUBMITTED"

                filled_quantity = latest.get("filled_quantity", 0)
                pending_quantity = latest.get("pending_quantity", 0)
                avg_price = latest.get("average_price", 0)

                # Extract fills from order history
                fills = []
                for entry in order_history:
                    if entry.get("filled_quantity", 0) > 0:
                        fills.append({
                            "timestamp": entry.get("exchange_update_timestamp", datetime.utcnow()).isoformat() + "Z"
                            if isinstance(entry.get("exchange_update_timestamp"), datetime)
                            else datetime.utcnow().isoformat() + "Z",
                            "quantity": entry.get("filled_quantity", 0),
                            "price": entry.get("average_price", 0)
                        })

                return {
                    "broker_order_id": broker_order_id,
                    "status": status,
                    "filled_quantity": filled_quantity,
                    "remaining_quantity": pending_quantity,
                    "avg_fill_price": avg_price,
                    "fills": fills
                }

            except Exception as kite_error:
                error_str = str(kite_error)

                if "not found" in error_str.lower() or "invalid" in error_str.lower():
                    raise OrderNotFoundError(
                        f"Order not found: {error_str}",
                        broker_name="Zerodha",
                        broker_order_id=broker_order_id
                    )
                else:
                    raise BrokerAPIError(f"Failed to get order status: {error_str}", broker_name="Zerodha")

        except OrderNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting order status: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get order status: {str(e)}", broker_name="Zerodha")

    # ========================================================================
    # ACCOUNT DATA
    # ========================================================================

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get account balance and equity.

        Args:
            account_id: Optional account ID (uses default from config if not provided)

        Returns:
            {
                "account_id": "AB1234",
                "equity": 250000.00,
                "cash_balance": 50000.00,
                "margin_used": 100000.00,
                "margin_available": 150000.00,
                "buying_power": 200000.00,
                "timestamp": "2025-01-07T12:00:00Z"
            }
        """
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to Zerodha", broker_name="Zerodha")

            # Get margins (contains balance and equity info)
            margins = self.kite.margins()

            # Zerodha returns margins for equity and commodity segments
            equity_margin = margins.get("equity", {})

            available_cash = equity_margin.get("available", {}).get("cash", 0)
            available_margin = equity_margin.get("available", {}).get("collateral", 0) + available_cash
            used_margin = equity_margin.get("utilised", {}).get("debits", 0)
            net = equity_margin.get("net", 0)

            return {
                "account_id": account_id or self.account_id,
                "equity": net,
                "cash_balance": available_cash,
                "margin_used": used_margin,
                "margin_available": available_margin,
                "buying_power": available_margin,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting account balance: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get account balance: {str(e)}", broker_name="Zerodha")

    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Args:
            account_id: Optional account ID

        Returns:
            [
                {
                    "symbol": "RELIANCE",
                    "quantity": 100,
                    "side": "LONG" | "SHORT",
                    "avg_price": 2500.00,
                    "current_price": 2520.00,
                    "unrealized_pnl": 2000.00,
                    "realized_pnl": 0.00,
                    "market_value": 252000.00
                }
            ]
        """
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to Zerodha", broker_name="Zerodha")

            # Get positions
            positions = self.kite.positions()

            # Zerodha returns both day and net positions
            net_positions = positions.get("net", [])

            open_positions = []
            for pos in net_positions:
                quantity = pos.get("quantity", 0)
                if quantity == 0:
                    continue  # Skip closed positions

                side = "LONG" if quantity > 0 else "SHORT"
                avg_price = pos.get("average_price", 0)
                last_price = pos.get("last_price", 0)
                pnl = pos.get("pnl", 0)

                open_positions.append({
                    "symbol": pos.get("tradingsymbol", ""),
                    "quantity": abs(quantity),
                    "side": side,
                    "avg_price": avg_price,
                    "current_price": last_price,
                    "unrealized_pnl": pnl,
                    "realized_pnl": pos.get("realised", 0),
                    "market_value": abs(quantity) * last_price
                })

            return open_positions

        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting open positions: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get open positions: {str(e)}", broker_name="Zerodha")

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
        try:
            balance = self.get_account_balance(account_id)

            margin_used = balance['margin_used']
            margin_available = balance['margin_available']
            equity = balance['equity']

            # Calculate leverage and utilization
            total_exposure = margin_used + margin_available
            leverage = (total_exposure / equity) if equity > 0 else 0
            margin_utilization_pct = (margin_used / equity * 100) if equity > 0 else 0

            return {
                "margin_used": margin_used,
                "margin_available": margin_available,
                "margin_requirement": margin_used,
                "excess_liquidity": margin_available,
                "leverage": leverage,
                "margin_utilization_pct": margin_utilization_pct
            }

        except Exception as e:
            logger.error(f"Error getting margin info: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get margin info: {str(e)}", broker_name="Zerodha")

    def get_open_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open (unfilled) orders.

        Args:
            account_id: Optional account ID

        Returns:
            [
                {
                    "broker_order_id": "210101000000123",
                    "symbol": "RELIANCE",
                    "side": "BUY",
                    "quantity": 100,
                    "order_type": "LIMIT",
                    "limit_price": 2500.00,
                    "status": "SUBMITTED",
                    "timestamp": "2025-01-07T12:00:00Z"
                }
            ]
        """
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to Zerodha", broker_name="Zerodha")

            # Get all orders
            all_orders = self.kite.orders()

            # Filter for open orders (not complete, cancelled, or rejected)
            open_orders = []
            for order in all_orders:
                status = order.get("status", "").upper()

                # Only include pending/open orders
                if status not in ["COMPLETE", "CANCELLED", "REJECTED"]:
                    open_orders.append({
                        "broker_order_id": str(order.get("order_id", "")),
                        "symbol": order.get("tradingsymbol", ""),
                        "side": order.get("transaction_type", ""),
                        "quantity": order.get("quantity", 0),
                        "order_type": order.get("order_type", ""),
                        "limit_price": order.get("price", 0),
                        "status": status,
                        "timestamp": order.get("order_timestamp", datetime.utcnow()).isoformat() + "Z"
                        if isinstance(order.get("order_timestamp"), datetime)
                        else datetime.utcnow().isoformat() + "Z"
                    })

            return open_orders

        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting open orders: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get open orders: {str(e)}", broker_name="Zerodha")
