"""
Interactive Brokers (IBKR) Broker Implementation
Uses ib_insync for connection and order management
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from ib_insync import IB, Stock, Option, Forex, Future, MarketOrder, LimitOrder

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
    BrokerTimeoutError
)

logger = logging.getLogger(__name__)


class IBKRBroker(AbstractBroker):
    """
    Interactive Brokers broker implementation using ib_insync.

    Example config:
    {
        "broker": "IBKR",
        "host": "127.0.0.1",
        "port": 7497,  # 7497 for TWS Paper, 7496 for TWS Live, 4002 for IB Gateway Paper, 4001 for IB Gateway Live
        "client_id": 1,
        "account_id": "DU123456"
    }
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize IBKR broker with configuration"""
        super().__init__(config)

        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7497)
        self.client_id = config.get("client_id", 1)

        # Initialize ib_insync connection object
        self.ib = IB()

        # Track active trades for order status queries
        self.active_trades = {}  # {order_id: ib_insync.Trade}

        logger.info(f"Initialized IBKR broker: {self.host}:{self.port} (client_id={self.client_id})")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self) -> bool:
        """
        Establish connection to Interactive Brokers TWS/Gateway.

        Returns:
            True if connection successful, False otherwise

        Raises:
            BrokerConnectionError: If connection fails
        """
        try:
            if self.is_connected():
                logger.info("Already connected to IBKR")
                return True

            logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id={self.client_id})")
            self.ib.connect(self.host, self.port, clientId=self.client_id)

            logger.info(f"✅ Successfully connected to IBKR")
            return True

        except Exception as e:
            error_msg = f"Failed to connect to IBKR at {self.host}:{self.port}: {str(e)}"
            logger.error(error_msg)
            raise BrokerConnectionError(error_msg, broker_name="IBKR", details={"host": self.host, "port": self.port})

    def disconnect(self) -> bool:
        """
        Close connection to IBKR.

        Returns:
            True if disconnection successful
        """
        try:
            if self.is_connected():
                self.ib.disconnect()
                logger.info("Disconnected from IBKR")
            return True

        except Exception as e:
            logger.error(f"Error disconnecting from IBKR: {e}")
            return False

    def is_connected(self) -> bool:
        """
        Check if currently connected to IBKR.

        Returns:
            True if connected, False otherwise
        """
        return self.ib.isConnected()

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    def _translate_direction_to_side(self, direction: str) -> str:
        """
        Translate internal direction to IBKR side.

        Args:
            direction: Internal direction ("LONG" or "SHORT")

        Returns:
            IBKR side ("BUY" or "SELL")
        """
        mapping = {
            'LONG': 'BUY',
            'SHORT': 'SELL'
        }
        direction_upper = direction.upper() if direction else ''
        return mapping.get(direction_upper, direction_upper)

    def _translate_order(self, internal_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate internal order schema to IBKR-specific schema.

        This method converts the universal internal order format used across
        the system to the IBKR-specific format expected by the broker API.

        Internal Schema (what ExecutionService sends):
        {
            'order_id': str,           # Internal tracking ID
            'strategy_id': str,        # Strategy identifier
            'instrument': str,         # Universal symbol (e.g., "AAPL", "AUDCAD")
            'instrument_type': str,    # "STOCK" | "OPTION" | "FOREX" | "FUTURE"
            'direction': str,          # "LONG" | "SHORT"
            'action': str,             # "ENTRY" | "EXIT" (not sent to broker)
            'quantity': float,         # Quantity
            'order_type': str,         # "MARKET" | "LIMIT"
            'limit_price': float,      # Optional: for LIMIT orders
            'legs': [...]              # Optional: for multi-leg options
        }

        IBKR Schema (what IBKR API expects):
        {
            'symbol': str,             # Renamed from 'instrument'
            'side': str,               # "BUY" | "SELL" (translated from direction)
            'quantity': int,           # Integer quantity
            'order_type': str,         # "MARKET" | "LIMIT"
            'limit_price': float,      # Optional
            'instrument_type': str,    # Pass-through
            'legs': [...]              # Pass-through for options
        }

        Args:
            internal_order: Standard internal order format

        Returns:
            IBKR-formatted order data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        logger.debug(f"Translating internal order to IBKR format: {internal_order.get('order_id', 'unknown')}")

        # Field name translations
        ibkr_order = {
            # Rename 'instrument' to 'symbol' and uppercase
            'symbol': internal_order.get('instrument', '').upper(),

            # Translate 'direction' to 'side' (LONG→BUY, SHORT→SELL)
            'side': self._translate_direction_to_side(internal_order.get('direction', '')),

            # Convert quantity to integer
            'quantity': int(internal_order.get('quantity', 0)),

            # Pass-through fields
            'order_type': internal_order.get('order_type', 'MARKET'),
            'instrument_type': internal_order.get('instrument_type', 'STOCK'),
        }

        # Conditional fields
        if 'limit_price' in internal_order and internal_order['limit_price']:
            ibkr_order['limit_price'] = internal_order['limit_price']

        if 'stop_price' in internal_order and internal_order['stop_price']:
            ibkr_order['stop_price'] = internal_order['stop_price']

        # Multi-leg support (for options) - pass through
        if 'legs' in internal_order and internal_order['legs']:
            ibkr_order['legs'] = internal_order['legs']

        # Pass through optional fields for specific instrument types
        if 'underlying' in internal_order:
            ibkr_order['underlying'] = internal_order['underlying']

        if 'expiry' in internal_order:
            ibkr_order['expiry'] = internal_order['expiry']

        if 'exchange' in internal_order:
            ibkr_order['exchange'] = internal_order['exchange']

        if 'account_id' in internal_order:
            ibkr_order['account_id'] = internal_order['account_id']

        logger.debug(f"Translated order - symbol: {ibkr_order.get('symbol')}, side: {ibkr_order.get('side')}, qty: {ibkr_order.get('quantity')}")
        return ibkr_order

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place an order with IBKR.

        This method accepts orders in the internal standard format and automatically
        translates them to IBKR-specific format before placement.

        Args:
            order: Order details in internal standard format
                {
                    "instrument": "AAPL",              # Universal symbol
                    "direction": "LONG" | "SHORT",    # Internal direction
                    "quantity": 100,                  # Can be float
                    "order_type": "MARKET" | "LIMIT",
                    "limit_price": 150.00,            # for LIMIT orders
                    "instrument_type": "STOCK" | "OPTION" | "FOREX" | "FUTURE",
                    "account_id": "DU123456",

                    # For options:
                    "underlying": "AAPL",
                    "legs": [
                        {"strike": 150, "expiry": "20250117", "right": "C", "action": "BUY", "quantity": 1}
                    ],

                    # For futures:
                    "expiry": "20250317",
                    "exchange": "NYMEX"
                }

        Returns:
            {
                "broker_order_id": "12345",
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
                raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")

            # Step 1: Translate internal order format to IBKR format
            order = self._translate_order(order)
            logger.info(f"Order translated for IBKR: {order.get('symbol')} {order.get('side')} {order.get('quantity')}")

            # Step 2: Validate required fields (now in IBKR format)
            symbol = order.get("symbol", "").strip()
            side = order.get("side", "").upper()
            quantity = order.get("quantity", 0)
            order_type = order.get("order_type", "MARKET").upper()
            instrument_type = order.get("instrument_type", "STOCK").upper()

            if not symbol and instrument_type != "OPTION":
                raise ValueError("Missing required field: 'symbol'")

            if side not in ["BUY", "SELL"]:
                raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")

            if quantity <= 0:
                raise ValueError(f"Invalid quantity: {quantity}. Must be > 0")

            # Create contract(s)
            contracts = self._create_contracts(order)

            # Submit orders (may be multiple legs for options)
            trades = []
            for contract_item in contracts:
                contract = contract_item['contract']
                leg_action = contract_item['action']
                leg_quantity = int(round(contract_item['quantity']))

                # Qualify contract with IBKR
                qualified_contracts = self.ib.qualifyContracts(contract)
                if not qualified_contracts:
                    raise InvalidSymbolError(
                        f"Failed to qualify contract: {contract}",
                        broker_name="IBKR",
                        symbol=str(contract)
                    )

                qualified_contract = qualified_contracts[0]
                logger.info(f"✅ Contract qualified: {qualified_contract}")

                # Create IBKR order
                if order_type == "MARKET":
                    ib_order = MarketOrder(leg_action, leg_quantity)
                elif order_type == "LIMIT":
                    limit_price = order.get("limit_price")
                    if not limit_price:
                        raise ValueError("limit_price required for LIMIT orders")
                    ib_order = LimitOrder(leg_action, leg_quantity, limit_price)
                else:
                    # Default to market
                    ib_order = MarketOrder(leg_action, leg_quantity)

                # Place order
                logger.info(f"📤 Placing order: {leg_action} {leg_quantity} {qualified_contract.symbol}")
                trade = self.ib.placeOrder(qualified_contract, ib_order)
                trades.append(trade)

            # Wait for order acknowledgment
            self.ib.sleep(2)

            # Check if any legs were rejected
            rejected_count = 0
            for i, trade in enumerate(trades, 1):
                status = trade.orderStatus.status
                if status in ['Cancelled', 'ApiCancelled', 'PendingCancel', 'Inactive']:
                    logger.error(f"❌ Leg {i} rejected by IBKR: {status}")
                    logger.error(f"   Trade log: {trade.log}")
                    rejected_count += 1

            if rejected_count > 0:
                raise OrderRejectedError(
                    f"{rejected_count}/{len(trades)} order legs rejected by IBKR",
                    broker_name="IBKR",
                    rejection_reason=f"Check logs for details"
                )

            # Determine overall status
            all_statuses = [t.orderStatus.status for t in trades]
            overall_status = all_statuses[0] if len(set(all_statuses)) == 1 else "Mixed"

            # Store trades for status queries
            broker_order_id = str(trades[0].order.orderId)
            self.active_trades[broker_order_id] = trades

            logger.info(f"✅ Order submitted successfully: {broker_order_id} ({len(trades)} legs)")

            return {
                "broker_order_id": broker_order_id,
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "message": f"Order submitted successfully ({len(trades)} legs)",
                "num_legs": len(trades)
            }

        except (BrokerConnectionError, OrderRejectedError, InvalidSymbolError):
            raise
        except ValueError as ve:
            raise OrderRejectedError(str(ve), broker_name="IBKR")
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to place order: {str(e)}", broker_name="IBKR")

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
        try:
            # Check if we have this order in our tracking
            if broker_order_id not in self.active_trades:
                raise OrderNotFoundError(
                    f"Order {broker_order_id} not found in active orders",
                    broker_name="IBKR",
                    broker_order_id=broker_order_id
                )

            trades = self.active_trades[broker_order_id]
            logger.info(f"🚫 Cancelling order {broker_order_id} ({len(trades)} legs)...")

            cancelled_count = 0
            for i, trade in enumerate(trades, 1):
                try:
                    status = trade.orderStatus.status
                    if status in ['Filled', 'Cancelled', 'ApiCancelled', 'Inactive']:
                        logger.info(f"   Leg {i} already {status} - skipping")
                        continue

                    self.ib.cancelOrder(trade.order)
                    cancelled_count += 1
                    logger.info(f"   ✓ Cancelled leg {i}")

                except Exception as e:
                    logger.error(f"   ✗ Error cancelling leg {i}: {e}")

            # Wait for cancellation to process
            self.ib.sleep(0.5)

            # Remove from tracking
            del self.active_trades[broker_order_id]
            logger.info(f"✅ Order {broker_order_id} cancelled ({cancelled_count}/{len(trades)} legs)")

            return cancelled_count > 0

        except OrderNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error cancelling order {broker_order_id}: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to cancel order: {str(e)}", broker_name="IBKR")

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
                    }
                ]
            }

        Raises:
            OrderNotFoundError: If order doesn't exist
        """
        try:
            if broker_order_id not in self.active_trades:
                raise OrderNotFoundError(
                    f"Order {broker_order_id} not found",
                    broker_name="IBKR",
                    broker_order_id=broker_order_id
                )

            trades = self.active_trades[broker_order_id]

            # Aggregate status from all legs
            total_filled = sum(t.orderStatus.filled for t in trades)
            total_remaining = sum(t.orderStatus.remaining for t in trades)
            all_statuses = [t.orderStatus.status for t in trades]

            # Determine overall status
            if total_remaining == 0 and total_filled > 0:
                status = "FILLED"
            elif total_filled > 0:
                status = "PARTIALLY_FILLED"
            elif 'Cancelled' in all_statuses or 'ApiCancelled' in all_statuses:
                status = "CANCELLED"
            else:
                status = "SUBMITTED"

            # Calculate average fill price
            if total_filled > 0:
                weighted_sum = sum(t.orderStatus.avgFillPrice * t.orderStatus.filled for t in trades)
                avg_fill_price = weighted_sum / total_filled
            else:
                avg_fill_price = 0

            # Get fills (simplified - would need execution details for full info)
            fills = []
            for trade in trades:
                if trade.orderStatus.filled > 0:
                    fills.append({
                        "timestamp": datetime.utcnow().isoformat() + "Z",  # Would need actual fill time
                        "quantity": trade.orderStatus.filled,
                        "price": trade.orderStatus.avgFillPrice
                    })

            return {
                "broker_order_id": broker_order_id,
                "status": status,
                "filled_quantity": total_filled,
                "remaining_quantity": total_remaining,
                "avg_fill_price": avg_fill_price,
                "fills": fills
            }

        except OrderNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting order status: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get order status: {str(e)}", broker_name="IBKR")

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
                "account_id": "DU123456",
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
                raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")

            account_values = self.ib.accountSummary()

            # Extract metrics
            equity = 0.0
            cash_balance = 0.0
            margin_used = 0.0
            margin_available = 0.0
            buying_power = 0.0

            for value in account_values:
                if value.tag == 'NetLiquidation':
                    equity = float(value.value)
                elif value.tag == 'TotalCashValue':
                    cash_balance = float(value.value)
                elif value.tag == 'MaintMarginReq':
                    margin_used = float(value.value)
                elif value.tag == 'AvailableFunds':
                    margin_available = float(value.value)
                elif value.tag == 'BuyingPower':
                    buying_power = float(value.value)

            return {
                "account_id": account_id or self.account_id,
                "equity": equity,
                "cash_balance": cash_balance,
                "margin_used": margin_used,
                "margin_available": margin_available,
                "buying_power": buying_power,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting account balance: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get account balance: {str(e)}", broker_name="IBKR")

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
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")

            positions = self.ib.positions()
            open_positions = []

            for pos in positions:
                side = "LONG" if pos.position > 0 else "SHORT"
                quantity = abs(pos.position)

                # avgCost in IBKR is already the average price per share
                avg_price = abs(pos.avgCost)

                # Request live market data for current price
                current_price = 0
                market_value = 0
                unrealized_pnl = 0

                try:
                    # Request market data snapshot
                    self.ib.reqMktData(pos.contract, snapshot=True)
                    self.ib.sleep(0.5)  # Brief wait for data

                    ticker = self.ib.ticker(pos.contract)
                    if ticker and ticker.marketPrice():
                        current_price = ticker.marketPrice()
                        market_value = current_price * quantity
                        unrealized_pnl = (current_price - avg_price) * quantity * (1 if side == "LONG" else -1)
                    else:
                        # Fallback: use avg_price if no market data available
                        market_value = avg_price * quantity

                except Exception as e:
                    logger.warning(f"Could not fetch market data for {pos.contract.symbol}: {e}")
                    market_value = avg_price * quantity

                open_positions.append({
                    "symbol": pos.contract.symbol,
                    "quantity": quantity,
                    "side": side,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "realized_pnl": 0,
                    "market_value": market_value
                })

            return open_positions

        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting open positions: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get open positions: {str(e)}", broker_name="IBKR")

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
            leverage = (margin_used + margin_available) / equity if equity > 0 else 0
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
            raise BrokerAPIError(f"Failed to get margin info: {str(e)}", broker_name="IBKR")

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
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")

            open_trades = self.ib.openTrades()
            orders_list = []

            for trade in open_trades:
                orders_list.append({
                    "broker_order_id": str(trade.order.orderId),
                    "symbol": trade.contract.symbol,
                    "side": trade.order.action,
                    "quantity": trade.order.totalQuantity,
                    "order_type": trade.order.orderType,
                    "limit_price": getattr(trade.order, 'lmtPrice', 0),
                    "status": trade.orderStatus.status,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })

            return orders_list

        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting open orders: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get open orders: {str(e)}", broker_name="IBKR")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _create_contracts(self, order: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create IBKR contract objects from order data.

        Returns:
            List of dicts: [{'contract': Contract, 'action': 'BUY'/'SELL', 'quantity': int}, ...]

        Raises:
            ValueError: If validation fails
        """
        instrument_type = order.get("instrument_type", "STOCK").upper()
        contracts = []

        if instrument_type == "STOCK":
            symbol = order["symbol"]
            contract = Stock(symbol=symbol, exchange='SMART', currency='USD')
            contracts.append({
                'contract': contract,
                'action': order.get("side", "BUY").upper(),
                'quantity': order.get("quantity", 0)
            })

        elif instrument_type == "OPTION":
            # Multi-leg options support
            legs = order.get("legs")
            if not legs or not isinstance(legs, list):
                raise ValueError("OPTION type requires 'legs' field as list")

            underlying = order.get("underlying", "").strip()
            if not underlying:
                raise ValueError("OPTION type requires 'underlying' field")

            for i, leg in enumerate(legs, 1):
                required_fields = ['strike', 'expiry', 'right', 'action', 'quantity']
                missing = [f for f in required_fields if f not in leg]
                if missing:
                    raise ValueError(f"Option leg {i} missing required fields: {missing}")

                # Validate right field
                right = leg['right'].upper()
                if right not in ['C', 'P', 'CALL', 'PUT']:
                    raise ValueError(f"Option leg {i} invalid 'right': {leg['right']}")

                if right == 'CALL':
                    right = 'C'
                elif right == 'PUT':
                    right = 'P'

                contract = Option(
                    symbol=underlying,
                    lastTradeDateOrContractMonth=str(leg['expiry']),
                    strike=float(leg['strike']),
                    right=right,
                    exchange='SMART'
                )

                contracts.append({
                    'contract': contract,
                    'action': leg['action'].upper(),
                    'quantity': int(leg['quantity'])
                })

        elif instrument_type == "FOREX":
            symbol = order["symbol"]
            if len(symbol) != 6:
                raise ValueError(f"FOREX instrument must be 6-character pair (e.g. EURUSD), got: {symbol}")

            contract = Forex(pair=symbol, exchange='IDEALPRO')
            contracts.append({
                'contract': contract,
                'action': order.get("side", "BUY").upper(),
                'quantity': order.get("quantity", 0)
            })

        elif instrument_type == "FUTURE":
            symbol = order["symbol"]
            expiry = order.get("expiry", "").strip()
            if not expiry:
                raise ValueError("FUTURE type requires 'expiry' field (YYYYMMDD)")

            exchange = order.get("exchange", "NYMEX").upper()

            contract = Future(
                symbol=symbol,
                lastTradeDateOrContractMonth=expiry,
                exchange=exchange
            )
            contracts.append({
                'contract': contract,
                'action': order.get("side", "BUY").upper(),
                'quantity': order.get("quantity", 0)
            })

        else:
            raise ValueError(f"Invalid instrument_type: {instrument_type}")

        return contracts
