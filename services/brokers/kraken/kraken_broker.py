"""
Kraken Broker Implementation
Crypto spot trading via Kraken REST API
"""
import logging
import time
import hmac
import hashlib
import base64
import urllib.parse
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import krakenex
except ImportError:
    krakenex = None

from services.brokers.base import AbstractBroker, OrderSide, OrderType, OrderStatus
from services.brokers.exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    BrokerAPIError,
    InvalidSymbolError
)

logger = logging.getLogger(__name__)


class KrakenBroker(AbstractBroker):
    """
    Kraken REST API broker implementation
    
    Supports:
    - Crypto spot trading (BTC, ETH, SOL, etc.)
    - Market and limit orders
    - Real-time balance queries
    - Real-time price data
    
    Symbol Format:
    - XBTUSD (BTC/USD)
    - ETHUSD (ETH/USD)
    - SOLUSD (SOL/USD)
    """
    
    # Symbol mapping: our format → Kraken format
    SYMBOL_MAP = {
        'BTC': 'XXBTZUSD',
        'XBTUSD': 'XXBTZUSD',
        'ETH': 'XETHZUSD',
        'ETHUSD': 'XETHZUSD',
        'SOL': 'SOLUSD',
        'SOLUSD': 'SOLUSD',
        'XRP': 'XXRPZUSD',
        'XRPUSD': 'XXRPZUSD',
        'ADA': 'ADAUSD',
        'ADAUSD': 'ADAUSD',
        'DOGE': 'XDGUSD',
        'DOGEUSD': 'XDGUSD'
    }
    
    # Reverse mapping for price ticker responses
    REVERSE_SYMBOL_MAP = {v: k for k, v in SYMBOL_MAP.items()}
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Kraken broker
        
        Config:
          - api_key: Kraken API key
          - api_secret: Kraken API secret
          - testnet: bool (not officially supported by Kraken, but for consistency)
        """
        super().__init__(config)
        
        if krakenex is None:
            raise BrokerConnectionError(
                "krakenex library not installed. Run: pip install krakenex",
                broker_name="Kraken"
            )
        
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.testnet = config.get('testnet', False)
        
        if not self.api_key or not self.api_secret:
            logger.warning("⚠️ Kraken API credentials not provided - connection will fail")
        
        # Initialize Kraken API client
        self.client = krakenex.API()
        self.client.key = self.api_key
        self.client.secret = self.api_secret
        
        self._connected = False
        self._last_balance_update = None
        self._cached_balance = None
        
        logger.info(f"Kraken broker initialized for account: {self.account_id}")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert our symbol format to Kraken format"""
        # Remove common suffixes
        symbol = symbol.upper().replace('-USD', '').replace('/USD', '')
        
        if symbol in self.SYMBOL_MAP:
            kraken_symbol = self.SYMBOL_MAP[symbol]
            logger.debug(f"Symbol mapping: {symbol} → {kraken_symbol}")
            return kraken_symbol
        
        # If no mapping found, try as-is
        logger.warning(f"No symbol mapping for {symbol}, using as-is")
        return symbol
    
    def _denormalize_symbol(self, kraken_symbol: str) -> str:
        """Convert Kraken symbol format back to our format"""
        if kraken_symbol in self.REVERSE_SYMBOL_MAP:
            return self.REVERSE_SYMBOL_MAP[kraken_symbol]
        return kraken_symbol
    
    # CONNECTION MANAGEMENT
    
    def connect(self) -> bool:
        """
        Test connection to Kraken API
        
        Returns:
            True if API credentials are valid
        """
        try:
            logger.info("Connecting to Kraken API...")
            
            # Test connection by querying server time
            response = self.client.query_public('Time')
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                raise BrokerConnectionError(
                    f"Kraken API error: {error_msg}",
                    broker_name="Kraken"
                )
            
            # Test private API with balance query
            balance_response = self.client.query_private('Balance')
            
            if balance_response.get('error'):
                error_msg = ', '.join(balance_response['error'])
                if 'Invalid key' in error_msg or 'EAPI:Invalid nonce' in error_msg:
                    raise BrokerConnectionError(
                        f"Kraken authentication failed: {error_msg}",
                        broker_name="Kraken"
                    )
                # Other errors might be acceptable (e.g., insufficient permissions)
                logger.warning(f"Kraken balance query warning: {error_msg}")
            
            self._connected = True
            logger.info("✅ Connected to Kraken API")
            return True
            
        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Kraken connection error: {e}", exc_info=True)
            raise BrokerConnectionError(
                f"Failed to connect to Kraken: {str(e)}",
                broker_name="Kraken"
            )
    
    def disconnect(self) -> bool:
        """
        Disconnect from Kraken API (no-op for REST API)
        """
        self._connected = False
        logger.info("Disconnected from Kraken API")
        return True
    
    def is_connected(self) -> bool:
        """Check if connected to Kraken API"""
        return self._connected
    
    # ORDER MANAGEMENT
    
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order on Kraken
        
        Args:
            order: Order details with keys:
                - instrument: Symbol (e.g., 'BTC', 'XBTUSD', 'ETHUSD')
                - side: 'BUY' or 'SELL'
                - quantity: Order quantity (in crypto units)
                - order_type: 'MARKET' or 'LIMIT'
                - price: Limit price (optional, for LIMIT orders)
        
        Returns:
            Order confirmation with:
                - broker_order_id: Kraken order ID
                - status: Order status
                - filled_quantity: Filled quantity
                - avg_fill_price: Average fill price
        """
        try:
            instrument = order.get('instrument')
            side = order.get('side', '').upper()
            quantity = float(order.get('quantity', 0))
            order_type = order.get('order_type', 'MARKET').upper()
            price = order.get('price')
            
            if not instrument or not side or quantity <= 0:
                raise OrderRejectedError(
                    "Invalid order: missing instrument, side, or quantity",
                    broker_name="Kraken"
                )
            
            # Normalize symbol
            kraken_symbol = self._normalize_symbol(instrument)
            
            # Map side
            kraken_side = 'buy' if side == 'BUY' else 'sell'
            
            # Prepare order parameters
            order_params = {
                'pair': kraken_symbol,
                'type': kraken_side,
                'ordertype': 'market' if order_type == 'MARKET' else 'limit',
                'volume': str(quantity),
                'validate': False  # Set to True for validation only
            }
            
            if order_type == 'LIMIT' and price:
                order_params['price'] = str(price)
            
            logger.info(f"📤 Placing Kraken order: {kraken_side.upper()} {quantity} {kraken_symbol} @ {order_type}")
            
            # Place order via API
            response = self.client.query_private('AddOrder', order_params)
            
            # Check for errors
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                raise OrderRejectedError(
                    f"Kraken order rejected: {error_msg}",
                    broker_name="Kraken",
                    order_id=order.get('order_id')
                )
            
            # Extract order ID
            result = response.get('result', {})
            txid_list = result.get('txid', [])
            broker_order_id = txid_list[0] if txid_list else None
            
            if not broker_order_id:
                raise BrokerAPIError(
                    "Kraken order placed but no order ID returned",
                    broker_name="Kraken"
                )
            
            # For market orders, Kraken fills immediately
            # Query order status to get fill details
            fill_info = self._get_order_status(broker_order_id)
            
            logger.info(f"✅ Kraken order placed: {broker_order_id}")
            
            return {
                'broker_order_id': broker_order_id,
                'status': fill_info.get('status', 'FILLED'),
                'filled_quantity': fill_info.get('filled_quantity', quantity),
                'avg_fill_price': fill_info.get('avg_fill_price', 0.0),
                'timestamp': datetime.utcnow().isoformat(),
                'description': result.get('descr', {}).get('order', '')
            }
            
        except (OrderRejectedError, BrokerAPIError):
            raise
        except Exception as e:
            logger.error(f"Error placing Kraken order: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to place Kraken order: {str(e)}",
                broker_name="Kraken"
            )
    
    def _get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Query order status from Kraken
        
        Returns:
            - status: FILLED, PARTIALLY_FILLED, CANCELLED, etc.
            - filled_quantity: Total filled quantity
            - avg_fill_price: Average fill price
        """
        try:
            response = self.client.query_private('QueryOrders', {'txid': order_id})
            
            if response.get('error'):
                logger.warning(f"Error querying order status: {response['error']}")
                return {
                    'status': 'SUBMITTED',
                    'filled_quantity': 0,
                    'avg_fill_price': 0
                }
            
            result = response.get('result', {})
            order_data = result.get(order_id, {})
            
            # Parse Kraken order status
            kraken_status = order_data.get('status', 'open')
            volume = float(order_data.get('vol', 0))
            volume_exec = float(order_data.get('vol_exec', 0))
            avg_price = float(order_data.get('price', 0))
            
            # Map Kraken status to our status
            if kraken_status == 'closed':
                status = 'FILLED'
            elif volume_exec > 0 and volume_exec < volume:
                status = 'PARTIALLY_FILLED'
            elif kraken_status == 'canceled':
                status = 'CANCELLED'
            else:
                status = 'SUBMITTED'
            
            return {
                'status': status,
                'filled_quantity': volume_exec,
                'avg_fill_price': avg_price
            }
            
        except Exception as e:
            logger.error(f"Error getting order status: {e}", exc_info=True)
            return {
                'status': 'SUBMITTED',
                'filled_quantity': 0,
                'avg_fill_price': 0
            }
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        try:
            response = self.client.query_private('CancelOrder', {'txid': order_id})
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                logger.error(f"Failed to cancel order {order_id}: {error_msg}")
                return False
            
            logger.info(f"✅ Cancelled Kraken order: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}", exc_info=True)
            return False
    
    # ACCOUNT DATA
    
    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get account balance from Kraken
        
        Returns:
            Dictionary with:
                - equity: Total account value in USD
                - cash_balance: Available cash in USD
                - margin_available: Available margin (same as cash for spot)
                - unrealized_pnl: 0 (Kraken spot doesn't track P&L)
                - last_updated: Timestamp
        """
        try:
            # Query balance
            response = self.client.query_private('Balance')
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                raise BrokerAPIError(
                    f"Failed to get Kraken balance: {error_msg}",
                    broker_name="Kraken"
                )
            
            balances = response.get('result', {})
            
            # Calculate total equity in USD
            # Kraken returns balances like: {'ZUSD': '10000.00', 'XXBT': '0.5', 'XETH': '5.0'}
            usd_balance = float(balances.get('ZUSD', 0))
            
            # For crypto balances, we'd need to convert to USD using current prices
            # For simplicity, we'll just use USD balance as equity
            total_equity = usd_balance
            
            # Add value of crypto holdings (if any)
            for asset, amount in balances.items():
                if asset != 'ZUSD' and float(amount) > 0:
                    # Try to get USD value of this asset
                    try:
                        # Map asset to symbol pair (e.g., XXBT → XXBTZUSD)
                        if asset == 'XXBT':
                            pair = 'XXBTZUSD'
                        elif asset == 'XETH':
                            pair = 'XETHZUSD'
                        elif asset.startswith('X') or asset.startswith('Z'):
                            # Try adding USD suffix
                            pair = f"{asset}USD"
                        else:
                            pair = f"{asset}USD"
                        
                        price = self._get_ticker_price(pair)
                        if price > 0:
                            total_equity += float(amount) * price
                            logger.debug(f"Added {amount} {asset} @ ${price} = ${float(amount) * price}")
                    except Exception as e:
                        logger.warning(f"Could not price {asset}: {e}")
            
            balance_data = {
                'base_currency': 'USD',
                'equity': total_equity,
                'cash_balance': usd_balance,
                'margin_available': usd_balance,  # Spot trading: margin = cash
                'margin_used': 0,
                'unrealized_pnl': 0,  # Kraken doesn't track P&L for spot
                'realized_pnl': 0,
                'last_updated': datetime.utcnow(),
                'raw_balances': balances  # Keep raw data for debugging
            }
            
            self._cached_balance = balance_data
            self._last_balance_update = datetime.utcnow()
            
            logger.info(f"💰 Kraken balance: ${total_equity:,.2f} (${usd_balance:,.2f} cash)")
            
            return balance_data
            
        except BrokerAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting Kraken balance: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to get account balance: {str(e)}",
                broker_name="Kraken"
            )
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get open positions
        
        Note: Kraken spot trading doesn't have "positions" concept
        Returns empty list or calculates positions from balance deltas
        """
        # For spot trading, we don't track positions
        # Could be implemented by comparing current balance to initial balance
        return []
    
    # MARKET DATA
    
    def get_current_price(self, instrument: str) -> float:
        """
        Get current market price for an instrument
        
        Args:
            instrument: Symbol (e.g., 'BTC', 'XBTUSD', 'ETHUSD')
        
        Returns:
            Current market price in USD
        """
        try:
            kraken_symbol = self._normalize_symbol(instrument)
            price = self._get_ticker_price(kraken_symbol)
            
            logger.debug(f"💹 Kraken price for {instrument}: ${price:,.2f}")
            return price
            
        except Exception as e:
            logger.error(f"Error getting Kraken price for {instrument}: {e}")
            raise BrokerAPIError(
                f"Failed to get price for {instrument}: {str(e)}",
                broker_name="Kraken"
            )
    
    def _get_ticker_price(self, kraken_symbol: str) -> float:
        """
        Get ticker price from Kraken API
        
        Args:
            kraken_symbol: Kraken format symbol (e.g., 'XXBTZUSD')
        
        Returns:
            Last trade price
        """
        try:
            response = self.client.query_public('Ticker', {'pair': kraken_symbol})
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                raise InvalidSymbolError(
                    f"Invalid symbol or API error: {error_msg}",
                    symbol=kraken_symbol,
                    broker_name="Kraken"
                )
            
            result = response.get('result', {})
            
            # Kraken returns ticker with various symbol formats
            # Try to find the matching key
            ticker_data = None
            for key in result.keys():
                if kraken_symbol in key or key in kraken_symbol:
                    ticker_data = result[key]
                    break
            
            if not ticker_data:
                # Try first key if only one result
                if len(result) == 1:
                    ticker_data = list(result.values())[0]
            
            if not ticker_data:
                raise InvalidSymbolError(
                    f"No ticker data found for {kraken_symbol}",
                    symbol=kraken_symbol,
                    broker_name="Kraken"
                )
            
            # Get last trade price: ticker_data['c'][0] is last trade price
            last_price = float(ticker_data['c'][0])
            
            return last_price
            
        except (InvalidSymbolError, BrokerAPIError):
            raise
        except Exception as e:
            logger.error(f"Error getting ticker for {kraken_symbol}: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to get ticker price: {str(e)}",
                broker_name="Kraken"
            )
    
    def get_order_book(self, instrument: str, depth: int = 10) -> Dict[str, Any]:
        """
        Get order book for an instrument
        
        Args:
            instrument: Symbol
            depth: Number of price levels (default: 10)
        
        Returns:
            Order book with bids and asks
        """
        try:
            kraken_symbol = self._normalize_symbol(instrument)
            
            response = self.client.query_public('Depth', {
                'pair': kraken_symbol,
                'count': depth
            })
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                raise BrokerAPIError(
                    f"Failed to get order book: {error_msg}",
                    broker_name="Kraken"
                )
            
            result = response.get('result', {})
            
            # Find matching symbol in result
            book_data = None
            for key in result.keys():
                if kraken_symbol in key or key in kraken_symbol:
                    book_data = result[key]
                    break
            
            if not book_data:
                book_data = list(result.values())[0] if result else {}
            
            return {
                'bids': book_data.get('bids', []),
                'asks': book_data.get('asks', []),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting order book: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to get order book: {str(e)}",
                broker_name="Kraken"
            )
    
    def get_margin_info(self) -> Dict[str, Any]:
        """
        Get margin information (not applicable for Kraken spot trading)
        
        Returns:
            Dict with margin info (all zeros for spot trading)
        """
        return {
            'margin_available': 0.0,
            'margin_used': 0.0,
            'margin_excess': 0.0,
            'maintenance_margin': 0.0
        }
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders
        
        Returns:
            List of open order dictionaries
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Kraken", broker_name="Kraken")
        
        try:
            response = self.client.query_private('OpenOrders')
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                logger.error(f"Failed to get open orders: {error_msg}")
                return []
            
            open_orders = []
            orders = response.get('result', {}).get('open', {})
            
            for order_id, order_data in orders.items():
                open_orders.append({
                    'order_id': order_id,
                    'symbol': order_data.get('descr', {}).get('pair', ''),
                    'side': order_data.get('descr', {}).get('type', '').upper(),
                    'quantity': float(order_data.get('vol', 0)),
                    'filled_quantity': float(order_data.get('vol_exec', 0)),
                    'order_type': order_data.get('descr', {}).get('ordertype', '').upper(),
                    'status': 'OPEN',
                    'created_at': datetime.fromtimestamp(order_data.get('opentm', 0)).isoformat()
                })
            
            return open_orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}", exc_info=True)
            return []
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order
        
        Args:
            order_id: Kraken order ID
            
        Returns:
            Dict with order status information
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Kraken", broker_name="Kraken")
        
        try:
            response = self.client.query_private('QueryOrders', {'txid': order_id})
            
            if response.get('error'):
                error_msg = ', '.join(response['error'])
                raise BrokerAPIError(
                    f"Failed to get order status: {error_msg}",
                    broker_name="Kraken"
                )
            
            orders = response.get('result', {})
            if not orders or order_id not in orders:
                return {
                    'order_id': order_id,
                    'status': 'UNKNOWN',
                    'message': 'Order not found'
                }
            
            order_data = orders[order_id]
            status_map = {
                'pending': 'PENDING',
                'open': 'OPEN',
                'closed': 'FILLED',
                'canceled': 'CANCELLED',
                'expired': 'EXPIRED'
            }
            
            return {
                'order_id': order_id,
                'status': status_map.get(order_data.get('status', 'unknown'), 'UNKNOWN'),
                'symbol': order_data.get('descr', {}).get('pair', ''),
                'side': order_data.get('descr', {}).get('type', '').upper(),
                'quantity': float(order_data.get('vol', 0)),
                'filled_quantity': float(order_data.get('vol_exec', 0)),
                'average_price': float(order_data.get('price', 0)),
                'created_at': datetime.fromtimestamp(order_data.get('opentm', 0)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting order status: {e}", exc_info=True)
            return {
                'order_id': order_id,
                'status': 'ERROR',
                'message': str(e)
            }
    
    def get_quantity_precision(self, instrument: str) -> int:
        """
        Get the quantity precision for an instrument
        
        Args:
            instrument: Symbol (e.g., 'BTC', 'ETH')
            
        Returns:
            Number of decimal places for quantity (default: 8 for crypto)
        """
        # Crypto typically uses 8 decimal places
        # Can be customized per symbol if needed
        precision_map = {
            'BTC': 8,
            'XBTUSD': 8,
            'ETH': 8,
            'ETHUSD': 8,
            'SOL': 4,
            'SOLUSD': 4,
            'XRP': 4,
            'XRPUSD': 4,
            'ADA': 4,
            'ADAUSD': 4,
            'DOGE': 2,
            'DOGEUSD': 2
        }
        
        return precision_map.get(instrument.upper(), 8)
    
    def __repr__(self):
        return f"<KrakenBroker account={self.account_id} connected={self._connected}>"
