"""
Interactive Brokers (IBKR) Broker Implementation
Uses ib_insync for connection and order management
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading
import asyncio
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from ib_insync import IB, Stock, Option, Forex, Future as IBFuture, Crypto, MarketOrder, LimitOrder

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

        # Connection settings: require config values (single source of truth)
        if "host" not in config:
            raise ValueError("IBKR config missing required field: 'host'")
        if "port" not in config:
            raise ValueError("IBKR config missing required field: 'port'")
        if "client_id" not in config:
            raise ValueError("IBKR config missing required field: 'client_id'")
        
        self.host = config["host"]
        self.port = int(config["port"])
        self.client_id = int(config["client_id"])
        
        # Market data type preference (optional from config)
        # 1=Live, 2=Frozen, 3=Delayed, 4=Delayed Frozen
        # If not specified, will be determined based on port with fallback
        self.market_data_type_preference = config.get("market_data_type")

        # Initialize ib_insync connection object
        self.ib = IB()

        # Track active trades for order status queries
        self.active_trades = {}  # {order_id: ib_insync.Trade}

        # Event loop for IB operations (runs in dedicated thread)
        self._ib_loop = None
        self._ib_thread = None

        logger.info(f"Initialized IBKR broker: {self.host}:{self.port} (client_id={self.client_id})")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self, skip_sync: bool = False) -> bool:
        """
        Establish connection to Interactive Brokers TWS/Gateway.

        Connection happens in a dedicated thread with its own event loop.

        Args:
            skip_sync: If True, skip waiting for positions/orders sync

        Returns:
            True if connection successful, False otherwise

        Raises:
            BrokerConnectionError: If connection fails after all retries
        """
        if self.is_connected():
            logger.info("Already connected to IBKR")
            return True

        # Start IB thread first, then connect within it
        self._start_ib_thread_and_connect(skip_sync)
        
        return self.is_connected()

    def _start_ib_thread_and_connect(self, skip_sync: bool):
        """Start dedicated thread, create event loop, and connect to IBKR within that thread"""
        import time
        from ib_insync import util
        
        connection_result = {'success': False, 'error': None}
        
        def ib_thread_main():
            """Main function for IB thread - creates loop and connects"""
            try:
                # Create event loop for this thread
                self._ib_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._ib_loop)
                
                logger.info("IB thread started, attempting connection...")
                
                # CRITICAL: Clean up stale connections before connecting
                # This prevents "Error 10197: No market data during competing live session"
                original_client_id = self.client_id
                logger.info(f"🧹 Cleaning up stale connections for client_id {original_client_id}...")
                try:
                    # Force disconnect any existing connection with our target client_id
                    cleanup_ib = IB()
                    cleanup_ib.connect(self.host, self.port, clientId=original_client_id, readonly=True, timeout=2)
                    util.sleep(0.1)
                    cleanup_ib.disconnect()
                    util.sleep(0.2)
                    logger.info(f"✅ Cleaned up stale connection for client_id {original_client_id}")
                except Exception as e:
                    # Expected if no stale connection exists
                    logger.debug(f"No stale connection to clean (normal): {e}")
                
                # Connection retry logic (same as before but in this thread)
                max_retries = 5
                
                for attempt in range(max_retries):
                    current_client_id = original_client_id + attempt
                    
                    try:
                        if attempt > 0:
                            try:
                                self.ib.disconnect()
                            except:
                                pass
                        
                        logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id={current_client_id})")
                        self.ib.connect(self.host, self.port, clientId=current_client_id, readonly=skip_sync)
                        
                        # Use util.sleep to wait in IB's loop
                        util.sleep(0.2 if skip_sync else 0.5)
                        
                        if self.ib.isConnected():
                            self.client_id = current_client_id
                            logger.info(f"✅ Successfully connected to IBKR (client_id={current_client_id})")
                            
                            # Configure market data
                            self._configure_market_data_type()
                            
                            connection_result['success'] = True
                            break
                        else:
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️ client_id={current_client_id} may be in use, trying next...")
                                try:
                                    self.ib.disconnect()
                                except:
                                    pass
                                util.sleep(0.5)
                            continue
                            
                    except Exception as e:
                        error_str = str(e).lower()
                        is_client_id_error = "326" in str(e) or "client id" in error_str
                        is_timeout = isinstance(e, TimeoutError) or "timeout" in error_str
                        
                        if (is_client_id_error or is_timeout) and attempt < max_retries - 1:
                            logger.warning(f"⚠️ client_id={current_client_id} may be in use, trying {current_client_id + 1}...")
                            try:
                                self.ib.disconnect()
                            except:
                                pass
                            util.sleep(0.5)
                            continue
                        
                        connection_result['error'] = str(e)
                        logger.error(f"Connection failed: {e}")
                        break
                
                if not connection_result['success'] and not connection_result['error']:
                    connection_result['error'] = f"Failed after {max_retries} attempts"
                
                if connection_result['success']:
                    # Keep loop running to process async tasks
                    logger.info("IB event loop running...")
                    self._ib_loop.run_forever()
                    logger.info("IB event loop stopped")
                else:
                    logger.error(f"Connection failed: {connection_result['error']}")
                    
            except Exception as e:
                logger.error(f"Fatal error in IB thread: {e}", exc_info=True)
                connection_result['error'] = str(e)
        
        # Start thread
        self._ib_thread = threading.Thread(target=ib_thread_main, daemon=True, name="IBThread")
        self._ib_thread.start()
        
        # Wait for connection to complete (max 15s)
        for i in range(150):  # 150 * 0.1s = 15s
            time.sleep(0.1)
            if connection_result['success'] or connection_result['error']:
                break
        
        if connection_result['error']:
            raise BrokerConnectionError(
                f"Failed to connect: {connection_result['error']}",
                broker_name="IBKR",
                details={"host": self.host, "port": self.port}
            )
        
        if not connection_result['success']:
            raise BrokerConnectionError(
                "Connection timeout",
                broker_name="IBKR",
                details={"host": self.host, "port": self.port}
            )
        
        logger.info("IB thread connected and running")

    def _configure_market_data_type(self):
        """
        Configure market data type with smart defaults and fallback.
        
        Priority:
        1. Use market_data_type from config if specified
        2. Auto-detect based on port (paper=4, live=1)
        3. Try type 1 (live) first, fallback to 3, then 4 if rejected
        
        Market Data Types:
        1 = Live (requires subscription)
        2 = Frozen (delayed 15-20 min, deprecated)
        3 = Delayed (10-15 min delay)
        4 = Delayed Frozen (most compatible for paper accounts)
        """
        # Determine preferred type
        if self.market_data_type_preference is not None:
            # Explicit preference from config
            preferred_type = int(self.market_data_type_preference)
            logger.info(f"📊 Using configured market_data_type: {preferred_type}")
        elif self.port in [4002, 4004, 7497]:  # Paper trading ports
            # Paper accounts: use delayed frozen (type 4) for compatibility
            # Live data (type 1) usually fails with Error 10197
            preferred_type = 4
            logger.info("📊 Paper account detected - using delayed/frozen market data (type 4)")
        else:  # Live ports (4001, 4003, 7496)
            # Live accounts: prefer live data
            preferred_type = 1
            logger.info("📊 Live account detected - requesting live market data (type 1)")
        
        # Try preferred type with fallback
        fallback_types = [3, 4]  # Delayed → Delayed Frozen
        types_to_try = [preferred_type] + [t for t in fallback_types if t != preferred_type]
        
        for market_data_type in types_to_try:
            try:
                self.ib.reqMarketDataType(market_data_type)
                logger.info(f"✅ Market data type set to: {market_data_type}")
                return  # Success!
            except Exception as e:
                if market_data_type == types_to_try[-1]:
                    # Last attempt failed
                    logger.warning(f"⚠️ All market data types failed. Last error: {e}")
                    logger.warning("⚠️ Market data may not be available. Will use default.")
                else:
                    # Try next type
                    logger.debug(f"Market data type {market_data_type} rejected: {e}. Trying fallback...")
                    continue

    def disconnect(self) -> bool:
        """
        Close connection to IBKR.

        Returns:
            True if disconnection successful
        """
        try:
            if self._ib_loop and self._ib_loop.is_running():
                self._ib_loop.stop()
            
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

    def _translate_direction_to_side(self, direction: str, instrument: str = None, account_id: str = None) -> str:
        """
        Translate internal direction to IBKR side.

        Args:
            direction: Internal direction ("LONG", "SHORT", or "CLOSE")
            instrument: Symbol (required if direction is "CLOSE")
            account_id: Account ID (required if direction is "CLOSE")

        Returns:
            IBKR side ("BUY" or "SELL")
        """
        mapping = {
            'LONG': 'BUY',
            'SHORT': 'SELL'
        }
        direction_upper = direction.upper() if direction else ''
        
        # Handle CLOSE direction - need to determine opposite side from position
        if direction_upper == 'CLOSE':
            if not instrument or not account_id:
                logger.warning(f"CLOSE direction requires instrument and account_id, but got instrument={instrument}, account_id={account_id}")
                return 'BUY'  # Default fallback
                
            try:
                # Get positions from account state
                positions = self.get_open_positions(account_id)
                for pos in positions:
                    if pos.get('instrument') == instrument:
                        pos_direction = pos.get('direction', '').upper()
                        # Close LONG position = SELL, Close SHORT position = BUY
                        return 'SELL' if pos_direction == 'LONG' else 'BUY'
                
                # No position found - default to BUY (safest for closing shorts)
                logger.warning(f"No position found for {instrument} in account {account_id}, defaulting CLOSE to BUY")
                return 'BUY'
            except Exception as e:
                logger.error(f"Error determining side for CLOSE order: {e}")
                return 'BUY'  # Default fallback
        
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

            # Translate 'direction' to 'side' (LONG→BUY, SHORT→SELL, CLOSE→depends on position)
            'side': self._translate_direction_to_side(
                internal_order.get('direction', ''),
                instrument=internal_order.get('instrument', ''),
                account_id=internal_order.get('account_id', '')
            ),

            # Quantity - pass through as float, precision should be applied before reaching here
            'quantity': float(internal_order.get('quantity', 0)),

            # Pass-through fields
            'order_type': internal_order.get('order_type', 'MARKET'),
            'instrument_type': internal_order.get('instrument_type', 'STOCK'),
        }

        # Conditional fields
        if 'limit_price' in internal_order and internal_order['limit_price']:
            ibkr_order['limit_price'] = internal_order['limit_price']

        if 'stop_price' in internal_order and internal_order['stop_price']:
            ibkr_order['stop_price'] = internal_order['stop_price']

        if 'price' in internal_order and internal_order['price']:
            ibkr_order['price'] = internal_order['price']

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

        Thread-safe: Submits async task to IB's dedicated event loop thread.

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
        if not self.is_connected():
            raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")

        if not self._ib_loop:
            raise BrokerAPIError("IB event loop not started", broker_name="IBKR")

        # Submit async task to IB's event loop from any thread
        future = asyncio.run_coroutine_threadsafe(
            self._place_order_async(order),
            self._ib_loop
        )
        
        # Wait for result with timeout
        try:
            return future.result(timeout=30.0)  # 30s timeout for order placement
        except TimeoutError:
            logger.error(f"⏱️ Timeout placing order")
            raise BrokerTimeoutError("Timeout placing order", broker_name="IBKR")
        except Exception as e:
            logger.error(f"Error in place_order future: {e}", exc_info=True)
            raise
        finally:
            if not future.done():
                future.cancel()

    async def _place_order_async(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Async coroutine to place order - runs in IB's event loop thread.
        """
        try:

            # Step 1: Translate internal order format to IBKR format
            order = self._translate_order(order)
            logger.info(f"Order translated for IBKR: {order.get('symbol')} {order.get('side')} {order.get('quantity')}")
            logger.info(f"🔍 DEBUG place_order Step 1: Order translated successfully")

            # Step 2: Validate required fields (now in IBKR format)
            symbol = order.get("symbol", "").strip()
            side = order.get("side", "").upper()
            quantity = order.get("quantity", 0)
            order_type = order.get("order_type", "MARKET").upper()
            instrument_type = order.get("instrument_type", "STOCK").upper()
            logger.info(f"🔍 DEBUG place_order Step 2: Extracted fields - symbol={symbol}, side={side}, qty={quantity}, type={order_type}, instrument_type={instrument_type}")

            if not symbol and instrument_type != "OPTION":
                raise ValueError("Missing required field: 'symbol'")

            if side not in ["BUY", "SELL"]:
                raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")

            if quantity <= 0:
                raise ValueError(f"Invalid quantity: {quantity}. Must be > 0")

            logger.info(f"🔍 DEBUG place_order Step 3: Validation passed, creating contracts...")
            # Create contract(s)
            contracts = self._create_contracts(order)
            logger.info(f"🔍 DEBUG place_order Step 4: Created {len(contracts)} contract(s)")

            # Submit orders (may be multiple legs for options)
            trades = []
            logger.info(f"🔍 DEBUG place_order Step 5: Starting loop through {len(contracts)} contract(s)")
            for i, contract_item in enumerate(contracts, 1):
                logger.info(f"🔍 DEBUG place_order Step 5.{i}: Processing contract {i}/{len(contracts)}")
                contract = contract_item['contract']
                leg_action = contract_item['action']
                # Apply broker precision to quantity
                symbol = order.get('symbol', '')
                precision = self.get_quantity_precision(symbol, instrument_type)
                raw_quantity = contract_item['quantity']
                if precision == 0:
                    leg_quantity = int(round(raw_quantity))
                else:
                    leg_quantity = round(raw_quantity, precision)
                logger.info(f"🔍 DEBUG place_order Step 5.{i}a: Quantity adjusted - raw={raw_quantity} → final={leg_quantity}")

                # Skip contract qualification to avoid hanging
                # For SMART exchange, IBKR handles routing without pre-qualification
                logger.info(f"🔍 DEBUG place_order Step 5.{i}b: Using contract directly (skipping qualification): {contract}")
                qualified_contract = contract
                logger.info(f"🔍 DEBUG place_order Step 5.{i}c: Contract ready for placement")

                # Create IBKR order
                logger.info(f"🔍 DEBUG place_order Step 5.{i}f: Creating IB order object (type={order_type})")
                if order_type == "MARKET":
                    ib_order = MarketOrder(leg_action, 0)  # Set totalQuantity to 0, will set below
                elif order_type == "LIMIT":
                    limit_price = order.get("limit_price")
                    if not limit_price:
                        raise ValueError("limit_price required for LIMIT orders")
                    ib_order = LimitOrder(leg_action, 0, limit_price)  # Set totalQuantity to 0
                else:
                    # Default to market
                    ib_order = MarketOrder(leg_action, 0)
                logger.info(f"🔍 DEBUG place_order Step 5.{i}g: IB order object created")

                # For CRYPTO, IBKR requires cashQty (USD amount) instead of totalQuantity
                if instrument_type == "CRYPTO":
                    logger.info(f"🔍 DEBUG place_order Step 5.{i}h: CRYPTO order - calculating cash quantity")
                    price = order.get("limit_price") or order.get("price", 0)
                    if price <= 0:
                        raise ValueError("CRYPTO orders require a price to calculate cash quantity")
                    cash_amount = round(leg_quantity * price, 2)  # USD amount
                    ib_order.cashQty = cash_amount
                    logger.info(f"📤 Placing CRYPTO order: {leg_action} ${cash_amount:.2f} USD of {qualified_contract.symbol}")
                else:
                    logger.info(f"🔍 DEBUG place_order Step 5.{i}h: Setting totalQuantity={leg_quantity}")
                    ib_order.totalQuantity = leg_quantity
                    logger.info(f"📤 Placing order: {leg_action} {leg_quantity} {qualified_contract.symbol}")
                
                # Set TIF for all order types - IBKR requires explicit TIF
                # IOC (Immediate or Cancel) for market orders, GTC (Good till Cancel) for limit orders
                ib_order.tif = "IOC" if order_type == "MARKET" else "GTC"
                
                logger.info(f"🔍 DEBUG place_order Step 5.{i}i: Connection status before placeOrder: {self.is_connected()}")
                logger.info(f"🔍 DEBUG place_order Step 5.{i}j: About to call ib.placeOrder()")
                trade = self.ib.placeOrder(qualified_contract, ib_order)
                logger.info(f"🔍 DEBUG place_order Step 5.{i}k: ib.placeOrder() RETURNED! Trade object: {trade}")
                trades.append(trade)
                logger.info(f"🔍 DEBUG place_order Step 5.{i}l: Trade added to list (total trades: {len(trades)})")

            # Wait for order acknowledgment
            logger.info(f"🔍 DEBUG place_order Step 6: All contracts processed, waiting 2s for acknowledgment...")
            await asyncio.sleep(2)
            logger.info(f"🔍 DEBUG place_order Step 7: Sleep complete, checking order status...")

            # Check if any legs were rejected
            rejected_count = 0
            rejection_messages = []
            for i, trade in enumerate(trades, 1):
                status = trade.orderStatus.status
                if status in ['Cancelled', 'ApiCancelled', 'PendingCancel', 'Inactive']:
                    logger.error(f"❌ Leg {i} rejected by IBKR: {status}")
                    logger.error(f"   Trade log: {trade.log}")
                    rejected_count += 1
                    
                    # Extract error messages from trade log
                    for log_entry in trade.log:
                        if log_entry.message and ('Error' in log_entry.message or 'rejected' in log_entry.message.lower()):
                            # Clean up HTML tags from IBKR error messages
                            clean_msg = log_entry.message.replace('<br>', ' ').replace('  ', ' ').strip()
                            rejection_messages.append(clean_msg)

            if rejected_count > 0:
                # Use the actual IBKR error message if available, otherwise fallback
                rejection_detail = "; ".join(rejection_messages) if rejection_messages else "Order rejected by IBKR (check logs for details)"
                raise OrderRejectedError(
                    f"{rejected_count}/{len(trades)} order legs rejected by IBKR",
                    broker_name="IBKR",
                    rejection_reason=rejection_detail
                )

            # Determine overall status
            all_statuses = [t.orderStatus.status for t in trades]
            overall_status = all_statuses[0] if len(set(all_statuses)) == 1 else "Mixed"

            # Store trades for status queries
            broker_order_id = str(trades[0].order.orderId)
            self.active_trades[broker_order_id] = trades

            # Get IBKR permanent confirmation ID (permId)
            # This is the broker's permanent order ID that persists across sessions
            perm_ids = [str(t.order.permId) for t in trades if t.order.permId]
            broker_confirmation_id = perm_ids[0] if perm_ids else None

            # Extract fill data from trades
            total_filled = sum(t.orderStatus.filled for t in trades)
            total_remaining = sum(t.orderStatus.remaining for t in trades)

            # Calculate average fill price (weighted by filled quantity)
            if total_filled > 0:
                weighted_sum = sum(t.orderStatus.avgFillPrice * t.orderStatus.filled for t in trades)
                avg_fill_price = weighted_sum / total_filled
            else:
                avg_fill_price = 0.0

            # Collect fills information
            fills = []
            for trade in trades:
                if trade.orderStatus.filled > 0:
                    fills.append({
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "quantity": trade.orderStatus.filled,
                        "price": trade.orderStatus.avgFillPrice
                    })

            logger.info(f"✅ Order submitted successfully: {broker_order_id} ({len(trades)} legs)")
            logger.info(f"   IBKR Confirmation ID (permId): {broker_confirmation_id}")
            logger.info(f"   Fill data: {total_filled} filled @ ${avg_fill_price:.4f}, {total_remaining} remaining")

            return {
                "broker_order_id": broker_order_id,
                "broker_confirmation_id": broker_confirmation_id,
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "message": f"Order submitted successfully ({len(trades)} legs)",
                "num_legs": len(trades),
                "filled": total_filled,
                "remaining": total_remaining,
                "avg_fill_price": avg_fill_price,
                "fills": fills
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

        Thread-safe: Runs in IB's dedicated event loop thread via call_soon_threadsafe.

        Args:
            broker_order_id: Broker's order ID

        Returns:
            True if cancellation successful

        Raises:
            OrderNotFoundError: If order doesn't exist
            BrokerAPIError: For API errors
        """
        if not self.is_connected():
            raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")
        
        if not self._ib_loop:
            raise BrokerAPIError("IB event loop not started", broker_name="IBKR")
        
        # Use Future to pass result from IB thread back to calling thread
        future = Future()
        
        def run_in_ib_thread():
            try:
                # Check if we have this order in our tracking
                if broker_order_id not in self.active_trades:
                    future.set_exception(OrderNotFoundError(
                        f"Order {broker_order_id} not found in active orders",
                        broker_name="IBKR",
                        broker_order_id=broker_order_id
                    ))
                    return

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

                future.set_result(cancelled_count > 0)
            except Exception as e:
                logger.error(f"Error cancelling order {broker_order_id}: {e}", exc_info=True)
                future.set_exception(BrokerAPIError(f"Failed to cancel order: {str(e)}", broker_name="IBKR"))
        
        # Submit to IB thread and wait for result
        self._ib_loop.call_soon_threadsafe(run_in_ib_thread)
        
        try:
            return future.result(timeout=10.0)
        except FuturesTimeoutError:
            logger.error(f"⏱️ Timeout cancelling order {broker_order_id}")
            raise BrokerTimeoutError(f"Timeout cancelling order {broker_order_id}", broker_name="IBKR")
        except Exception as e:
            # Exception was already set by run_in_ib_thread
            raise

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

        Thread-safe: Submits async task to IB's dedicated event loop thread.

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
        if not self.is_connected():
            raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")
        
        if not self._ib_loop:
            raise BrokerAPIError("IB event loop not started", broker_name="IBKR")
        
        # Submit async task to IB's event loop from any thread
        future = asyncio.run_coroutine_threadsafe(
            self._get_account_balance_async(account_id),
            self._ib_loop
        )
        
        # Wait for result with timeout
        try:
            return future.result(timeout=10.0)
        except FuturesTimeoutError:
            logger.error(f"⏱️ Timeout getting account balance")
            raise BrokerTimeoutError("Timeout getting account balance", broker_name="IBKR")
        except Exception as e:
            logger.error(f"Error in get_account_balance future: {e}", exc_info=True)
            raise
        finally:
            if not future.done():
                future.cancel()

    async def _get_account_balance_async(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Async coroutine to get account balance - runs in IB's event loop thread.
        Uses accountSummaryAsync() which is safe for already-running event loops.
        """
        try:
            # Use async version since event loop is already running
            # accountSummary() calls run_until_complete() internally which fails
            account_summary = await self.ib.accountSummaryAsync()
            
            logger.info(f"Account summary items: {len(account_summary)}")

            # Extract metrics - IBKR returns values in account's base currency
            equity = 0.0
            cash_balance = 0.0
            margin_used = 0.0
            margin_available = 0.0
            buying_power = 0.0
            unrealized_pnl = 0.0
            realized_pnl = 0.0

            for item in account_summary:
                if item.tag == 'NetLiquidation':
                    equity = float(item.value)
                    logger.info(f"NetLiquidation: {item.value} {item.currency}")
                elif item.tag == 'TotalCashValue':
                    cash_balance = float(item.value)
                elif item.tag == 'MaintMarginReq':
                    margin_used = float(item.value)
                elif item.tag == 'AvailableFunds':
                    margin_available = float(item.value)
                elif item.tag == 'BuyingPower':
                    buying_power = float(item.value)
                elif item.tag == 'UnrealizedPnL':
                    unrealized_pnl = float(item.value)
                elif item.tag == 'RealizedPnL':
                    realized_pnl = float(item.value)

            return {
                "account_id": account_id or self.account_id,
                "equity": equity,
                "cash_balance": cash_balance,
                "margin_used": margin_used,
                "margin_available": margin_available,
                "buying_power": buying_power,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except Exception as e:
            logger.error(f"Error in _get_account_balance_async: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get account balance: {str(e)}", broker_name="IBKR")

    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Thread-safe: Submits async task to IB's dedicated event loop thread.

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
        if not self.is_connected():
            raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")
        
        if not self._ib_loop:
            raise BrokerAPIError("IB event loop not started", broker_name="IBKR")
        
        # Submit async task to IB's event loop from any thread
        future = asyncio.run_coroutine_threadsafe(
            self._get_open_positions_async(account_id),
            self._ib_loop
        )
        
        # Wait for result with timeout
        try:
            return future.result(timeout=10.0)
        except FuturesTimeoutError:
            logger.error(f"⏱️ Timeout getting open positions")
            raise BrokerTimeoutError("Timeout getting open positions", broker_name="IBKR")
        except Exception as e:
            logger.error(f"Error in get_open_positions future: {e}", exc_info=True)
            raise
        finally:
            if not future.done():
                future.cancel()

    async def _get_open_positions_async(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Async coroutine to get open positions - runs in IB's event loop thread.
        Uses reqPositionsAsync() which is safe for already-running event loops.
        """
        try:
            # Use async version since event loop is already running
            # positions() calls run_until_complete() internally which fails
            # Request positions and wait for them
            await self.ib.reqPositionsAsync()
            positions = self.ib.positions()
            open_positions = []

            for pos in positions:
                side = "LONG" if pos.position > 0 else "SHORT"
                quantity = abs(pos.position)

                # avgCost in IBKR is already the average price per share
                avg_price = abs(pos.avgCost)

                # NOTE: Disabled live market data requests to avoid competing with execution service
                # IBKR Paper accounts only allow 1 concurrent live data subscription
                # Account data service doesn't need real-time prices - use average cost instead
                current_price = avg_price  # Use avg_price instead of requesting live data
                market_value = avg_price * quantity
                unrealized_pnl = 0  # Cannot calculate without current price

                open_positions.append({
                    "instrument": pos.contract.symbol,
                    "quantity": quantity,
                    "side": side,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "realized_pnl": 0,
                    "market_value": market_value
                })

            return open_positions

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
    # MARKET DATA (for paper_live mode pricing)
    # ========================================================================

    def get_market_price(self, symbol: str, instrument_type: str) -> float:
        """
        Get current market price for an instrument.

        Thread-safe: Submits async task to IB's dedicated event loop thread.

        Args:
            symbol: Asset symbol (e.g., "AAPL", "EURUSD", "BTC")
            instrument_type: Type of instrument ("STOCK", "FOREX", "CRYPTO", "FUTURE", "OPTION")

        Returns:
            Current market price (mid-price or last traded price)

        Raises:
            BrokerConnectionError: If not connected
            BrokerAPIError: If no market data available
        """
        if not self.is_connected():
            raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")
        
        if not self._ib_loop:
            raise BrokerAPIError("IB event loop not started", broker_name="IBKR")
        
        # Submit async task to IB's event loop from any thread
        future = asyncio.run_coroutine_threadsafe(
            self._fetch_price_async(symbol, instrument_type),
            self._ib_loop
        )
        
        # Wait for result with timeout, ensuring cleanup on all error paths
        try:
            return future.result(timeout=10.0)
        except TimeoutError:
            # Timeout usually means no market data available (market closed, data permissions, or invalid symbol)
            logger.warning(f"⏱️ Timeout fetching price for {symbol} - no data received within 10s")
            raise BrokerAPIError(
                f"No market data available for {symbol}. Possible reasons: market closed, no data subscription, or invalid symbol.",
                broker_name="IBKR"
            )
        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}"
            logger.error(f"Error fetching price for {symbol}: {error_msg}")
            raise BrokerAPIError(f"Failed to get market price: {error_msg}", broker_name="IBKR")
        finally:
            # Ensure the future is cancelled if it's still pending (cleanup guarantee)
            if not future.done():
                logger.debug(f"🧹 Cancelling pending future for {symbol} price fetch")
                future.cancel()

    async def _fetch_price_async(self, symbol: str, instrument_type: str) -> float:
        """
        Async coroutine to fetch price - runs in IB's event loop thread.
        """
        contract = None
        ticker = None
        
        try:
            # Create contract
            contract = self._create_contract_for_pricing(symbol, instrument_type)

            # Request market data (snapshot=True for one-time data, avoids subscription conflicts)
            ticker = self.ib.reqMktData(contract, '', True, False)  # snapshot=True

            # Wait for data using asyncio.sleep() - we're in the right loop now
            logger.info(f"⏳ Waiting for market data for {symbol}...")
            
            import math
            for i in range(100):  # 100 * 0.1s = 10s max
                await asyncio.sleep(0.1)
                
                # Check if we have valid (not nan) data
                has_bid = ticker.bid and not math.isnan(ticker.bid) and ticker.bid > 0
                has_ask = ticker.ask and not math.isnan(ticker.ask) and ticker.ask > 0
                has_last = ticker.last and not math.isnan(ticker.last) and ticker.last > 0
                
                if has_bid or has_ask or has_last:
                    logger.info(f"✅ Market data received after {(i+1)*0.1:.1f}s: bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}")
                    break

            # Return mid-price if available, otherwise last price
            if ticker.bid and ticker.ask and not math.isnan(ticker.bid) and not math.isnan(ticker.ask) and ticker.bid > 0 and ticker.ask > 0:
                price = (ticker.bid + ticker.ask) / 2
                logger.info(f"📊 Market price for {symbol}: ${price:.2f} (bid=${ticker.bid:.2f}, ask=${ticker.ask:.2f})")
                return price
            elif ticker.last and not math.isnan(ticker.last) and ticker.last > 0:
                logger.warning(f"⚠️ Using last price for {symbol}: ${ticker.last:.2f}")
                return ticker.last
            else:
                raise BrokerAPIError(
                    f"No market data available for {symbol} ({instrument_type})",
                    broker_name="IBKR"
                )
        except Exception as e:
            if "BrokerAPIError" in str(type(e)):
                raise
            # Provide more detailed error message
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Error in _fetch_price_async for {symbol}: {error_msg}", exc_info=True)
            raise BrokerAPIError(f"Failed to fetch price: {error_msg}", broker_name="IBKR")
        finally:
            # CRITICAL: Always cancel market data subscription to avoid accumulating subscriptions
            if ticker is not None and contract is not None:
                try:
                    self.ib.cancelMktData(contract)
                    logger.debug(f"🧹 Cleaned up market data subscription for {symbol}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup market data for {symbol}: {cleanup_error}")

    def _create_contract_for_pricing(self, symbol: str, instrument_type: str):
        """
        Create a simple IBKR contract for market data requests.

        This is a simplified version that creates contracts suitable for pricing queries.
        """
        from ib_insync import Stock, Forex, Crypto, Future as IBFuture

        instrument_type = instrument_type.upper()

        if instrument_type == "STOCK" or instrument_type == "ETF":
            return Stock(symbol, 'SMART', 'USD')

        elif instrument_type == "FOREX":
            # Handle both formats: "EURUSD" or "EUR.USD"
            # IBKR's Forex() class expects exactly 6 characters (e.g., "EURUSD")
            if '.' in symbol:
                # Remove dot from "EUR.USD" -> "EURUSD"
                pair = symbol.replace('.', '')
            else:
                pair = symbol
            
            # Validate length
            if len(pair) != 6:
                raise BrokerAPIError(
                    f"Invalid forex pair format: '{symbol}'. Expected 6-character format like 'EURUSD' or 'EUR.USD'",
                    broker_name="IBKR"
                )
            return Forex(pair)

        elif instrument_type == "CRYPTO":
            # For crypto, IBKR uses PAXOS exchange
            return Crypto(symbol, 'PAXOS', 'USD')

        elif instrument_type == "FUTURE":
            # For futures, we need more info, but try a basic contract
            # In production, this should be enhanced with expiry/exchange from order data
            logger.warning(f"Creating basic future contract for {symbol} - may need enhancement")
            return IBFuture(symbol, exchange='SMART')

        elif instrument_type == "OPTION":
            # Options require strike/expiry - should not be called for options
            # In paper_live mode, option pricing should come from order data
            logger.warning(f"get_market_price() called for OPTION {symbol} - returning 0")
            raise BrokerAPIError(
                f"Cannot get market price for OPTIONS without strike/expiry. "
                f"Use order data for option pricing.",
                broker_name="IBKR"
            )

        else:
            raise BrokerAPIError(
                f"Unsupported instrument type for pricing: {instrument_type}",
                broker_name="IBKR"
            )

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

        elif instrument_type == "CRYPTO":
            symbol = order["symbol"]
            # IBKR uses PAXOS exchange for crypto trading
            contract = Crypto(symbol=symbol, exchange='PAXOS', currency='USD')
            contracts.append({
                'contract': contract,
                'action': order.get("side", "BUY").upper(),
                'quantity': order.get("quantity", 0)
            })

        else:
            raise ValueError(f"Invalid instrument_type: {instrument_type}")

        return contracts

    # ========================================================================
    # QUANTITY PRECISION
    # ========================================================================

    def get_quantity_precision(self, symbol: str, instrument_type: str) -> int:
        """
        Get the number of decimal places allowed for quantity.

        Uses static defaults to avoid blocking calls to IBKR during order placement.
        Previous implementation queried IBKR's qualifyContracts() which could hang.

        Args:
            symbol: Asset symbol (e.g., "AAPL", "EURUSD")
            instrument_type: Type of instrument

        Returns:
            int: Number of decimal places (0 for integers)
        """
        # Use default precision values to avoid hanging during order placement
        # IBKR qualifyContracts() and reqContractDetails() can block indefinitely
        return self._get_default_precision(instrument_type)

    def _get_default_precision(self, instrument_type: str) -> int:
        """
        Get default precision when IBKR query fails.

        Args:
            instrument_type: Type of instrument

        Returns:
            Default number of decimal places
        """
        defaults = {
            'STOCK': 0,
            'ETF': 0,
            'OPTION': 0,
            'FUTURE': 0,
            'FOREX': 0,  # IBKR uses whole units for forex
            'CRYPTO': 8,
        }
        return defaults.get(instrument_type.upper(), 0)

    # ========================================================================
    # MARGIN PREVIEW (whatIfOrder)
    # ========================================================================

    def get_order_margin_impact(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get margin impact for a hypothetical order using IBKR's whatIfOrder API.

        This queries IBKR for the actual margin requirements before placing an order.

        Args:
            order: Order details in internal standard format
                {
                    "instrument": "GC",
                    "direction": "LONG" | "SHORT",
                    "quantity": 2,
                    "order_type": "MARKET" | "LIMIT",
                    "instrument_type": "FUTURE",
                    "expiry": "20250224",
                    "exchange": "COMEX"
                }

        Returns:
            {
                "init_margin_change": 22000.00,    # Additional initial margin required
                "maint_margin_change": 20000.00,   # Additional maintenance margin required
                "init_margin_after": 122000.00,    # Total initial margin after trade
                "maint_margin_after": 110000.00,   # Total maintenance margin after trade
                "equity_with_loan": 250000.00,     # Equity with loan value
                "commission": 5.00,                # Estimated commission
                "success": True
            }

        Raises:
            BrokerConnectionError: If not connected
            BrokerAPIError: For API errors
        """
        try:
            # Ensure connected
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR", broker_name="IBKR")

            # Translate order to IBKR format
            ibkr_order = self._translate_order(order)
            logger.info(f"Getting margin impact for: {ibkr_order.get('symbol')} {ibkr_order.get('side')} {ibkr_order.get('quantity')}")

            # Create contract
            contracts = self._create_contracts(ibkr_order)
            if not contracts:
                raise ValueError("Failed to create contract for margin query")

            contract_item = contracts[0]
            contract = contract_item['contract']
            leg_action = contract_item['action']
            leg_quantity = int(round(contract_item['quantity']))

            # Qualify contract with IBKR
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                raise InvalidSymbolError(
                    f"Failed to qualify contract for margin query: {contract}",
                    broker_name="IBKR",
                    symbol=str(contract)
                )

            qualified_contract = qualified_contracts[0]
            logger.debug(f"Qualified contract for margin query: {qualified_contract}")

            # Create order object for whatIfOrder
            order_type = ibkr_order.get("order_type", "MARKET").upper()
            if order_type == "MARKET":
                ib_order = MarketOrder(leg_action, leg_quantity)
            elif order_type == "LIMIT":
                limit_price = ibkr_order.get("limit_price", 0)
                if not limit_price:
                    # For limit orders without price, use market order for margin calc
                    ib_order = MarketOrder(leg_action, leg_quantity)
                else:
                    ib_order = LimitOrder(leg_action, leg_quantity, limit_price)
            else:
                ib_order = MarketOrder(leg_action, leg_quantity)

            # Call whatIfOrder to get margin impact
            logger.info(f"📊 Querying IBKR whatIfOrder for margin impact...")
            what_if_result = self.ib.whatIfOrder(qualified_contract, ib_order)

            # Wait briefly for result
            self.ib.sleep(1)

            if not what_if_result:
                raise BrokerAPIError(
                    "whatIfOrder returned empty result",
                    broker_name="IBKR"
                )

            # Extract margin data from result
            # whatIfOrder returns an OrderState object with margin fields
            init_margin_change = float(what_if_result.initMarginChange or 0)
            maint_margin_change = float(what_if_result.maintMarginChange or 0)
            init_margin_after = float(what_if_result.initMarginAfter or 0)
            maint_margin_after = float(what_if_result.maintMarginAfter or 0)
            equity_with_loan = float(what_if_result.equityWithLoanAfter or 0)
            commission = float(what_if_result.commission or 0)

            logger.info(f"✅ Margin impact retrieved:")
            logger.info(f"   Initial Margin Change: ${init_margin_change:,.2f}")
            logger.info(f"   Maintenance Margin Change: ${maint_margin_change:,.2f}")
            logger.info(f"   Commission: ${commission:,.2f}")

            return {
                "init_margin_change": init_margin_change,
                "maint_margin_change": maint_margin_change,
                "init_margin_after": init_margin_after,
                "maint_margin_after": maint_margin_after,
                "equity_with_loan": equity_with_loan,
                "commission": commission,
                "success": True
            }

        except (BrokerConnectionError, InvalidSymbolError):
            raise
        except Exception as e:
            logger.error(f"Error getting margin impact: {e}", exc_info=True)
            raise BrokerAPIError(f"Failed to get margin impact: {str(e)}", broker_name="IBKR")
