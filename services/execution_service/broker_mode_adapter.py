"""
Broker Mode Adapter - Routes data and execution to different brokers based on environment

This adapter enables mock_live mode by wrapping multiple brokers:
- Data operations (get prices, market data) → routed to data_broker (e.g., IBKR for live data)
- Execution operations (place orders, cancel) → routed to execution_broker (e.g., Mock for unlimited funds)

Environment-based override logic (HIGH-LEVEL SAFETY):
- staging environment → ALWAYS use mock or paper execution (never live)
- live environment → ONLY allow live execution

Use Cases:
1. mock_live: IBKR (data) + Mock (execution) → unlimited virtual funds with realistic prices
2. paper_live: IBKR (data + execution) → limited paper account with real IBKR simulation
3. live_live: IBKR (data + execution) → real money trading

Safety Features:
- Environment override: staging + live account → OVERRIDE to mock (logged)
- Validation: live + paper/mock → ERROR rejected
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import broker interfaces
from brokers import AbstractBroker, OrderSide, OrderType, OrderStatus
from brokers.exceptions import BrokerConnectionError, OrderRejectedError

logger = logging.getLogger(__name__)


class BrokerModeAdapter:
    """
    Adapter that routes operations to different brokers based on mode
    
    Implements the same AbstractBroker interface so it can be used transparently
    by the execution service
    """
    
    def __init__(self, data_broker: AbstractBroker, execution_broker: AbstractBroker, 
                 environment: str, account_type: str, mode: str):
        """
        Initialize the adapter with separate data and execution brokers
        
        Args:
            data_broker: Broker for market data (e.g., IBKR for live prices)
            execution_broker: Broker for order execution (e.g., Mock for virtual trading)
            environment: 'staging' or 'live'
            account_type: 'mock', 'paper', or 'live'
            mode: Trading mode like 'mock_live', 'paper_live', etc.
        """
        self.data_broker = data_broker
        self.execution_broker = execution_broker
        self.environment = environment
        self.account_type = account_type
        self.mode = mode
        
        logger.info(f"BrokerModeAdapter initialized:")
        logger.info(f"  Environment: {environment}")
        logger.info(f"  Account Type: {account_type}")
        logger.info(f"  Mode: {mode}")
        logger.info(f"  Data Broker: {data_broker.broker_name if data_broker else 'None'}")
        logger.info(f"  Execution Broker: {execution_broker.broker_name if execution_broker else 'None'}")
    
    # ============================================================================
    # AbstractBroker Implementation - Route methods to appropriate broker
    # ============================================================================
    
    @property
    def broker_name(self) -> str:
        """Return combined broker name"""
        if self.data_broker == self.execution_broker:
            return self.data_broker.broker_name
        return f"{self.execution_broker.broker_name}(exec)+{self.data_broker.broker_name}(data)"
    
    @property
    def is_connected(self) -> bool:
        """Both brokers must be connected"""
        data_connected = self.data_broker.is_connected if self.data_broker else True
        exec_connected = self.execution_broker.is_connected if self.execution_broker else True
        return data_connected and exec_connected
    
    def connect(self) -> bool:
        """Connect both brokers"""
        success = True
        
        if self.data_broker:
            try:
                data_success = self.data_broker.connect()
                if not data_success:
                    logger.error(f"Failed to connect data broker: {self.data_broker.broker_name}")
                    success = False
            except Exception as e:
                logger.error(f"Error connecting data broker: {e}")
                success = False
        
        if self.execution_broker and self.execution_broker != self.data_broker:
            try:
                exec_success = self.execution_broker.connect()
                if not exec_success:
                    logger.error(f"Failed to connect execution broker: {self.execution_broker.broker_name}")
                    success = False
            except Exception as e:
                logger.error(f"Error connecting execution broker: {e}")
                success = False
        
        return success
    
    def disconnect(self) -> bool:
        """Disconnect both brokers"""
        success = True
        
        if self.data_broker:
            try:
                self.data_broker.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting data broker: {e}")
                success = False
        
        if self.execution_broker and self.execution_broker != self.data_broker:
            try:
                self.execution_broker.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting execution broker: {e}")
                success = False
        
        return success
    
    # ============================================================================
    # Market Data Operations - Route to data_broker
    # ============================================================================
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from data broker"""
        if not self.data_broker:
            logger.error("No data broker configured")
            return None
        return self.data_broker.get_current_price(symbol)
    
    def get_market_data(self, symbol: str, data_type: str = 'quote') -> Optional[Dict[str, Any]]:
        """Get market data from data broker"""
        if not self.data_broker:
            logger.error("No data broker configured")
            return None
        return self.data_broker.get_market_data(symbol, data_type)
    
    def get_account_value(self, value_type: str = 'NetLiquidation') -> Optional[float]:
        """Get account value from execution broker (where the account actually is)"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return None
        return self.execution_broker.get_account_value(value_type)
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions from execution broker"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return []
        return self.execution_broker.get_positions()
    
    # ============================================================================
    # Order Execution Operations - Route to execution_broker
    # ============================================================================
    
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order via execution broker
        
        This is where mock_live magic happens: orders go to Mock broker 
        (unlimited funds) but with LIVE market prices from data broker
        
        Args:
            order: Order dict following AbstractBroker interface
        
        Returns:
            Result dict from execution broker
        """
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return {"status": "REJECTED", "reason": "No execution broker configured"}
        
        logger.info(f"🔀 BrokerModeAdapter routing order to execution broker: {self.execution_broker.broker_name}")
        logger.info(f"   Order: {order.get('direction')} {order.get('quantity')} {order.get('instrument')}")
        
        # CRITICAL: For mock_live mode, fetch LIVE price from data_broker
        # This ensures mock execution uses realistic market prices, not hardcoded values
        if self.mode == 'mock_live' and self.data_broker and self.data_broker != self.execution_broker:
            symbol = order.get('instrument')
            instrument_type = order.get('instrument_type', 'STOCK')
            if symbol:
                try:
                    # Try get_market_price (IBKR) or get_current_price (fallback)
                    if hasattr(self.data_broker, 'get_market_price'):
                        live_price = self.data_broker.get_market_price(symbol, instrument_type)
                    elif hasattr(self.data_broker, 'get_current_price'):
                        live_price = self.data_broker.get_current_price(symbol)
                    else:
                        live_price = None
                        logger.warning(f"   ⚠️  Data broker {self.data_broker.broker_name} has no price method")
                    
                    if live_price and live_price > 0:
                        original_price = order.get('price')
                        order['price'] = live_price
                        logger.info(f"   💰 Updated order price: ${original_price} → ${live_price:.2f} (LIVE from {self.data_broker.broker_name})")
                    else:
                        logger.warning(f"   ⚠️  Could not fetch live price for {symbol}, using order price: ${order.get('price')}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Error fetching live price for {symbol}: {e}, using order price")
        
        # Pass order dict to execution broker (follows AbstractBroker interface)
        return self.execution_broker.place_order(order)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order via execution broker"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return False
        return self.execution_broker.cancel_order(order_id)
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get order status from execution broker"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return None
        return self.execution_broker.get_order_status(order_id)
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get open orders from execution broker"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return []
        return self.execution_broker.get_open_orders()
    
    # ============================================================================
    # Account Operations - Route to execution_broker
    # ============================================================================
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary from execution broker"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return {}
        return self.execution_broker.get_account_summary()
    
    def get_buying_power(self) -> Optional[float]:
        """Get buying power from execution broker"""
        if not self.execution_broker:
            logger.error("No execution broker configured")
            return None
        return self.execution_broker.get_buying_power()


def create_broker_adapter(environment: str, account_type: str, data_source: str,
                         broker_pool: Dict[str, Any]) -> AbstractBroker:
    """
    Factory function to create appropriate broker or adapter based on environment/account/data
    
    Environment-based override logic (HIGH-LEVEL SAFETY):
    - staging + live account → OVERRIDE to mock (logged as WARNING)
    - live + paper/mock account → ERROR rejected
    
    Args:
        environment: 'staging' or 'live'
        account_type: 'mock', 'paper', or 'live'
        data_source: 'mock' or 'live'
        broker_pool: Dict of available brokers {'mock': ..., 'ibkr_paper': ..., 'ibkr_live': ...}
    
    Returns:
        BrokerInterface or BrokerModeAdapter
    """
    
    # ============================================================================
    # ENVIRONMENT OVERRIDE LOGIC (HIGH-LEVEL SAFETY)
    # ============================================================================
    
    original_account_type = account_type
    
    # STAGING OVERRIDE: Never allow live execution in staging
    if environment == 'staging' and account_type == 'live':
        logger.warning("=" * 80)
        logger.warning("⚠️  ENVIRONMENT OVERRIDE TRIGGERED")
        logger.warning(f"   Original: environment={environment}, account_type={account_type}")
        logger.warning(f"   Override: account_type='mock' (staging cannot use live accounts)")
        logger.warning("   Safety: All orders will use Mock broker (unlimited virtual funds)")
        logger.warning("=" * 80)
        account_type = 'mock'
    
    # LIVE VALIDATION: Only allow live accounts in live environment
    if environment == 'live' and account_type in ['mock', 'paper']:
        error_msg = f"Safety check failed: environment={environment} cannot use account_type={account_type}"
        logger.error("=" * 80)
        logger.error(f"❌ {error_msg}")
        logger.error("   Live environment ONLY supports live accounts (real money)")
        logger.error("   Use environment='staging' for mock/paper testing")
        logger.error("=" * 80)
        raise ValueError(error_msg)
    
    # ============================================================================
    # DETERMINE MODE AND SELECT BROKERS
    # ============================================================================
    
    # Determine trading mode
    if account_type == 'mock' and data_source == 'mock':
        mode = 'mock_mock'
    elif account_type == 'mock' and data_source == 'live':
        mode = 'mock_live'
    elif account_type == 'paper' and data_source == 'live':
        mode = 'paper_live'
    elif account_type == 'live' and data_source == 'live':
        mode = 'live_live'
    else:
        # Fallback
        mode = f"{account_type}_{data_source}"
    
    logger.info(f"Creating broker adapter: environment={environment}, account_type={account_type}, data_source={data_source}")
    logger.info(f"  Determined mode: {mode}")
    
    if original_account_type != account_type:
        logger.info(f"  (overridden from account_type={original_account_type})")
    
    # ============================================================================
    # CASE 1: mock_mock - Mock broker for both data and execution
    # ============================================================================
    if mode == 'mock_mock':
        mock_broker = broker_pool.get('mock')
        if not mock_broker:
            raise ValueError("Mock broker not available in broker pool")
        logger.info(f"  Using Mock broker for both data and execution")
        return mock_broker
    
    # ============================================================================
    # CASE 2: mock_live - IBKR for data, Mock for execution (YOUR MAIN USE CASE)
    # ============================================================================
    elif mode == 'mock_live':
        ibkr_broker = broker_pool.get('ibkr_paper')  # Use paper IBKR for data
        mock_broker = broker_pool.get('mock')
        
        if not ibkr_broker:
            raise ValueError("IBKR broker not available for live data source")
        if not mock_broker:
            raise ValueError("Mock broker not available for execution")
        
        logger.info(f"  Using BrokerModeAdapter:")
        logger.info(f"    - Data: IBKR (live market prices)")
        logger.info(f"    - Execution: Mock (unlimited virtual funds)")
        
        return BrokerModeAdapter(
            data_broker=ibkr_broker,
            execution_broker=mock_broker,
            environment=environment,
            account_type=account_type,
            mode=mode
        )
    
    # ============================================================================
    # CASE 3: paper_live - IBKR paper for both data and execution
    # ============================================================================
    elif mode == 'paper_live':
        ibkr_paper = broker_pool.get('ibkr_paper')
        if not ibkr_paper:
            raise ValueError("IBKR paper broker not available")
        logger.info(f"  Using IBKR paper broker for both data and execution")
        return ibkr_paper
    
    # ============================================================================
    # CASE 4: live_live - IBKR live for both data and execution
    # ============================================================================
    elif mode == 'live_live':
        ibkr_live = broker_pool.get('ibkr_live')
        if not ibkr_live:
            raise ValueError("IBKR live broker not available")
        logger.info(f"  Using IBKR live broker for both data and execution (REAL MONEY)")
        return ibkr_live
    
    else:
        raise ValueError(f"Unsupported mode: {mode}")
