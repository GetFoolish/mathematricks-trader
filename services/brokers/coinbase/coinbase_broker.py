"""
Coinbase Advanced Trade API Broker Implementation
Supports crypto spot trading with official sandbox environment
"""
import logging
import time
import jwt
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

try:
    from coinbase.rest import RESTClient
except ImportError:
    RESTClient = None

from services.brokers.base import AbstractBroker, OrderSide, OrderType, OrderStatus
from services.brokers.exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    BrokerAPIError,
    InvalidSymbolError
)

logger = logging.getLogger(__name__)


class CoinbaseBroker(AbstractBroker):
    """
    Coinbase Advanced Trade API broker implementation
    
    Supports:
    - Crypto spot trading (BTC, ETH, SOL, etc.)
    - Market and limit orders
    - Real-time balance queries
    - Sandbox environment for testing
    
    Symbol Format:
    - BTC-USD (Bitcoin)
    - ETH-USD (Ethereum)
    - SOL-USD (Solana)
    """
    
    # Symbol mapping: our format → Coinbase format
    SYMBOL_MAP = {
        'BTC': 'BTC-USD',
        'BTC-USD': 'BTC-USD',
        'ETH': 'ETH-USD',
        'ETH-USD': 'ETH-USD',
        'SOL': 'SOL-USD',
        'SOL-USD': 'SOL-USD',
        'XRP': 'XRP-USD',
        'XRP-USD': 'XRP-USD',
        'ADA': 'ADA-USD',
        'ADA-USD': 'ADA-USD',
        'DOGE': 'DOGE-USD',
        'DOGE-USD': 'DOGE-USD'
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Coinbase broker
        
        Config:
          - api_key: Coinbase API key name (e.g., organizations/xxx/apiKeys/yyy)
          - api_secret: Coinbase private key (PEM format string)
          - sandbox: bool (use sandbox environment)
        """
        super().__init__(config)
        
        if RESTClient is None:
            raise BrokerConnectionError(
                "coinbase-advanced-py library not installed. Run: pip install coinbase-advanced-py",
                broker_name="Coinbase"
            )
        
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.sandbox = config.get('sandbox', False)
        
        if not self.api_key or not self.api_secret:
            logger.warning("⚠️ Coinbase API credentials not provided - connection will fail")
        
        # Coinbase-specific workaround: Sandbox lacks price/data endpoints
        # Always use production for data reads, sandbox only for orders
        self.data_api_url = "https://api.coinbase.com"  # Always production for prices/data
        self.order_api_url = "https://api-sandbox.coinbase.com" if self.sandbox else "https://api.coinbase.com"
        
        try:
            # Data client: Always production (sandbox lacks market data endpoints)
            self.data_client = RESTClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                base_url=self.data_api_url
            )
            
            # Order client: Respects sandbox flag
            self.order_client = RESTClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                base_url=self.order_api_url
            )
            
            # Main client points to order_client for compatibility
            self.client = self.order_client
            
        except Exception as e:
            logger.error(f"Failed to initialize Coinbase clients: {e}")
            self.data_client = None
            self.order_client = None
            self.client = None
        
        self._connected = False
        self._last_balance_update = None
        self._cached_balance = None
        
        logger.info(f"Coinbase broker initialized for account: {self.account_id}")
        logger.info(f"  Data API: {self.data_api_url} (production for market data)")
        logger.info(f"  Order API: {self.order_api_url} ({'sandbox' if self.sandbox else 'production'})")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to Coinbase format
        
        Args:
            symbol: Symbol in various formats (BTC, BTC-USD, etc.)
            
        Returns:
            Coinbase symbol format (BTC-USD)
        """
        symbol_upper = symbol.upper().strip()
        
        if symbol_upper in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[symbol_upper]
        
        # If already in correct format
        if '-' in symbol_upper and symbol_upper.endswith('USD'):
            return symbol_upper
        
        raise InvalidSymbolError(
            f"Symbol '{symbol}' not recognized. Supported: {list(self.SYMBOL_MAP.keys())}",
            symbol=symbol,
            broker_name="Coinbase"
        )
    
    def connect(self) -> bool:
        """
        Test connection to Coinbase API
        
        Returns:
            True if connection successful
        """
        if not self.data_client or not self.order_client:
            logger.error("Coinbase clients not initialized")
            return False
        
        try:
            logger.info("Testing Coinbase API connection...")
            
            # Test connection by getting accounts (use data_client for reads)
            accounts = self.data_client.get_accounts()
            
            if not accounts or not hasattr(accounts, 'accounts'):
                logger.error("Failed to retrieve accounts from Coinbase")
                return False
            
            logger.info(f"✅ Connected to Coinbase API - {len(accounts.accounts)} accounts found")
            self._connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Coinbase: {e}", exc_info=True)
            self._connected = False
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from Coinbase (no explicit disconnect needed for REST API)
        
        Returns:
            True
        """
        self._connected = False
        logger.info("Disconnected from Coinbase")
        return True
    
    def is_connected(self) -> bool:
        """
        Check if connected to Coinbase
        
        Returns:
            Connection status
        """
        return self._connected
    
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order on Coinbase
        
        Args:
            order: Order dict with keys:
                - instrument: Symbol (BTC, ETH, etc.)
                - action: BUY or SELL
                - quantity: Order quantity
                - order_type: MARKET or LIMIT
                - limit_price: Price for limit orders (optional)
                
        Returns:
            Order confirmation with broker_order_id
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            symbol = self._normalize_symbol(order['instrument'])
            action = order['action'].upper()
            quantity = str(order['quantity'])
            order_type = order.get('order_type', 'MARKET').upper()
            
            logger.info(f"Placing {order_type} {action} order: {quantity} {symbol}")
            
            # Map to Coinbase order format
            side = 'BUY' if action == 'BUY' else 'SELL'
            
            # Use order_client for placing orders (respects sandbox flag)
            if order_type == 'MARKET':
                # Market order
                response = self.order_client.market_order(
                    product_id=symbol,
                    side=side,
                    base_size=quantity
                )
            else:
                # Limit order
                limit_price = str(order.get('limit_price', 0))
                response = self.order_client.limit_order_gtc(
                    product_id=symbol,
                    side=side,
                    base_size=quantity,
                    limit_price=limit_price
                )
            
            if not response or not hasattr(response, 'success'):
                raise OrderRejectedError(
                    f"Order rejected by Coinbase: Invalid response",
                    broker_name="Coinbase"
                )
            
            if not response.success:
                error_msg = getattr(response, 'failure_reason', 'Unknown error')
                raise OrderRejectedError(
                    f"Order rejected: {error_msg}",
                    broker_name="Coinbase"
                )
            
            order_id = response.order_id if hasattr(response, 'order_id') else 'UNKNOWN'
            
            logger.info(f"✅ Order placed successfully - Order ID: {order_id}")
            
            return {
                'broker_order_id': order_id,
                'status': 'FILLED' if order_type == 'MARKET' else 'PENDING',
                'filled_quantity': float(quantity) if order_type == 'MARKET' else 0,
                'average_price': self.get_current_price(symbol) if order_type == 'MARKET' else 0,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except (InvalidSymbolError, OrderRejectedError, BrokerConnectionError):
            raise
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to place order: {str(e)}",
                broker_name="Coinbase"
            )
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order on Coinbase
        
        Args:
            order_id: Broker order ID
            
        Returns:
            True if cancelled successfully
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            # Use order_client for cancelling orders
            response = self.order_client.cancel_orders(order_ids=[order_id])
            
            if response and hasattr(response, 'results'):
                for result in response.results:
                    if result.success:
                        logger.info(f"✅ Order {order_id} cancelled")
                        return True
            
            logger.warning(f"Failed to cancel order {order_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}", exc_info=True)
            return False
    
    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get account balance from Coinbase
        
        Returns:
            Dict with balance information
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            # Use data_client for reading account balance
            accounts_response = self.data_client.get_accounts()
            
            if not accounts_response or not hasattr(accounts_response, 'accounts'):
                raise BrokerAPIError(
                    "Failed to get accounts from Coinbase",
                    broker_name="Coinbase"
                )
            
            total_equity = 0.0
            cash_balance = 0.0
            holdings = {}
            
            for account in accounts_response.accounts:
                currency = account.currency
                available = float(account.available_balance.value) if hasattr(account.available_balance, 'value') else 0.0
                
                if currency == 'USD':
                    cash_balance = available
                    total_equity += available
                else:
                    # Get current price for crypto holdings
                    try:
                        symbol = f"{currency}-USD"
                        price = self.get_current_price(symbol)
                        value = available * price
                        total_equity += value
                        
                        if available > 0:
                            holdings[currency] = available
                    except:
                        logger.warning(f"Could not price {currency}")
            
            balance = {
                'base_currency': 'USD',
                'equity': total_equity,
                'cash_balance': cash_balance,
                'margin_available': total_equity,  # Spot trading, no margin
                'margin_used': 0.0,
                'unrealized_pnl': 0.0,
                'realized_pnl': 0.0,
                'holdings': holdings,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            self._cached_balance = balance
            self._last_balance_update = datetime.utcnow()
            
            return balance
            
        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting account balance: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to get account balance: {str(e)}",
                broker_name="Coinbase"
            )
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get open positions (crypto holdings)
        
        For spot trading, this returns current crypto holdings
        
        Returns:
            List of position dictionaries
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            balance = self.get_account_balance()
            holdings = balance.get('holdings', {})
            
            positions = []
            for currency, quantity in holdings.items():
                if quantity > 0:
                    symbol = f"{currency}-USD"
                    try:
                        current_price = self.get_current_price(symbol)
                        positions.append({
                            'instrument': symbol,
                            'quantity': quantity,
                            'side': 'LONG',
                            'average_price': current_price,  # Spot: use current price
                            'current_price': current_price,
                            'unrealized_pnl': 0.0,  # Cannot calculate without entry price
                            'market_value': quantity * current_price
                        })
                    except Exception as e:
                        logger.warning(f"Could not get position for {symbol}: {e}")
            
            return positions
            
        except BrokerConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error getting positions: {e}", exc_info=True)
            return []
    
    def get_current_price(self, instrument: str) -> float:
        """
        Get current market price for an instrument
        
        Args:
            instrument: Symbol (BTC, ETH, BTC-USD, etc.)
            
        Returns:
            Current price
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            symbol = self._normalize_symbol(instrument)
            
            # Use data_client for getting prices (always production)
            ticker = self.data_client.get_product(product_id=symbol)
            
            if not ticker or not hasattr(ticker, 'price'):
                raise BrokerAPIError(
                    f"Failed to get price for {symbol}",
                    broker_name="Coinbase"
                )
            
            price = float(ticker.price)
            logger.debug(f"Current price for {symbol}: ${price:,.2f}")
            
            return price
            
        except (InvalidSymbolError, BrokerConnectionError):
            raise
        except Exception as e:
            logger.error(f"Error getting current price: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to get price: {str(e)}",
                broker_name="Coinbase"
            )
    
    def get_order_book(self, instrument: str, depth: int = 10) -> Dict[str, Any]:
        """
        Get order book for an instrument
        
        Args:
            instrument: Symbol
            depth: Order book depth
            
        Returns:
            Order book with bids and asks
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            symbol = self._normalize_symbol(instrument)
            
            # Use data_client for getting order book (always production)
            book = self.data_client.get_product_book(product_id=symbol, limit=depth)
            
            if not book:
                raise BrokerAPIError(
                    f"Failed to get order book for {symbol}",
                    broker_name="Coinbase"
                )
            
            return {
                'bids': [[float(bid.price), float(bid.size)] for bid in (book.bids or [])][:depth],
                'asks': [[float(ask.price), float(ask.size)] for ask in (book.asks or [])][:depth],
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting order book: {e}", exc_info=True)
            raise BrokerAPIError(
                f"Failed to get order book: {str(e)}",
                broker_name="Coinbase"
            )
    
    def get_margin_info(self) -> Dict[str, Any]:
        """
        Get margin information (not applicable for Coinbase spot trading)
        
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
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            # Use order_client for querying orders
            orders_response = self.order_client.list_orders(order_status='OPEN')
            
            if not orders_response or not hasattr(orders_response, 'orders'):
                return []
            
            open_orders = []
            for order in orders_response.orders:
                open_orders.append({
                    'order_id': order.order_id,
                    'symbol': order.product_id,
                    'side': order.side,
                    'quantity': float(order.order_configuration.base_size) if hasattr(order.order_configuration, 'base_size') else 0,
                    'filled_quantity': float(order.filled_size) if hasattr(order, 'filled_size') else 0,
                    'order_type': 'MARKET' if hasattr(order.order_configuration, 'market_market_ioc') else 'LIMIT',
                    'status': order.status,
                    'created_at': order.created_time
                })
            
            return open_orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}", exc_info=True)
            return []
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order
        
        Args:
            order_id: Coinbase order ID
            
        Returns:
            Dict with order status information
        """
        if not self._connected:
            raise BrokerConnectionError("Not connected to Coinbase", broker_name="Coinbase")
        
        try:
            # Use order_client for querying order status
            order = self.order_client.get_order(order_id=order_id)
            
            if not order:
                return {
                    'order_id': order_id,
                    'status': 'UNKNOWN',
                    'message': 'Order not found'
                }
            
            return {
                'order_id': order.order_id,
                'status': order.status,
                'symbol': order.product_id,
                'side': order.side,
                'quantity': float(order.order_configuration.base_size) if hasattr(order.order_configuration, 'base_size') else 0,
                'filled_quantity': float(order.filled_size) if hasattr(order, 'filled_size') else 0,
                'average_price': float(order.average_filled_price) if hasattr(order, 'average_filled_price') else 0,
                'created_at': order.created_time
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
        precision_map = {
            'BTC': 8,
            'BTC-USD': 8,
            'ETH': 8,
            'ETH-USD': 8,
            'SOL': 4,
            'SOL-USD': 4,
            'XRP': 4,
            'XRP-USD': 4,
            'ADA': 4,
            'ADA-USD': 4,
            'DOGE': 2,
            'DOGE-USD': 2
        }
        
        return precision_map.get(instrument.upper(), 8)
    
    def __repr__(self):
        return f"<CoinbaseBroker account={self.account_id} connected={self._connected} sandbox={self.sandbox}>"
