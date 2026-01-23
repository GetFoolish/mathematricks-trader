"""
BrokerModeAdapter - Hybrid adapter for 4-mode trading system

This adapter wraps real broker + mock broker instances to enable:
- mock_mock: Mock account + Mock data (fully simulated, fast testing)
- mock_live: Mock account + Live data (strategy testing with real market data)
- paper_live: IBKR paper account + Live data (true IBKR paper trading on port 4004)
- live_live: Live account + Live data (production trading, real money)

The adapter routes method calls based on account_type and data_source fields from trading_accounts collection.

Mode is computed as: {account_type}_{data_source}
- account_type: mock | paper | live (where orders execute)
- data_source: mock | live (where data comes from)
"""
from typing import Dict, Any, List, Optional
from services.brokers.base import AbstractBroker
from services.brokers.exceptions import BrokerAPIError
import logging

logger = logging.getLogger(__name__)


class BrokerModeAdapter(AbstractBroker):
    """
    Adapter that wraps real broker + mock broker instances for mode-based routing.

    Modes (computed from account_type × data_source):
    - mock_mock: All calls to mock broker with mock pricing
    - mock_live: Pricing from real broker, orders to mock broker
    - paper_live: All calls to real broker (IBKR paper account on port 4004)
    - live_live: All calls to real broker (production)
    """

    def __init__(
        self, 
        real_broker: AbstractBroker, 
        mock_broker: Optional[AbstractBroker], 
        account_type: str,
        data_source: str
    ):
        """
        Initialize the adapter with broker instances.

        Args:
            real_broker: Real broker instance (e.g., IBKRBroker)
            mock_broker: Mock broker instance (optional for paper_live/live_live)
            account_type: Account type - "mock" | "paper" | "live"
            data_source: Data source - "mock" | "live"
        """
        # Validate inputs
        if account_type not in ['mock', 'paper', 'live']:
            raise ValueError(f"Invalid account_type: {account_type}. Must be mock|paper|live")
        if data_source not in ['mock', 'live']:
            raise ValueError(f"Invalid data_source: {data_source}. Must be mock|live")
        
        # Compute mode for backward compatibility
        mode = f"{account_type}_{data_source}"
        
        # Create a combined config for the base class
        config = {
            "broker": f"{real_broker.broker_name}_Adapter",
            "account_id": real_broker.account_id or (mock_broker.account_id if mock_broker else "unknown"),
            "mode": mode,
            "account_type": account_type,
            "data_source": data_source
        }
        super().__init__(config)

        self.real_broker = real_broker
        self.mock_broker = mock_broker
        self.account_type = account_type
        self.data_source = data_source
        self.mode = mode  # Computed field for convenience

        logger.info(f"BrokerModeAdapter initialized for account {self.account_id}")
        logger.info(f"  Account Type: {account_type} (where orders execute)")
        logger.info(f"  Data Source: {data_source} (where data comes from)")
        logger.info(f"  Computed Mode: {mode}")
        logger.info(f"  Real broker: {real_broker.broker_name}")
        if mock_broker:
            logger.info(f"  Mock broker: {mock_broker.broker_name}")

    # CONNECTION MANAGEMENT

    def connect(self) -> bool:
        """
        Connect to appropriate broker(s) based on account_type and data_source.

        - mock_mock: Connect only to mock
        - mock_live: Connect to both (need real for pricing)
        - paper_live: Connect only to real (IBKR paper account)
        - live_live: Connect only to real
        """
        try:
            if self.account_type == "mock" and self.data_source == "mock":
                # mock_mock: Only mock broker needed
                if not self.mock_broker:
                    raise BrokerAPIError("Mock broker required for mock_mock mode")
                result = self.mock_broker.connect()
                logger.info(f"[{self.mode}] Connected to mock broker: {result}")
                return result

            elif self.account_type == "mock" and self.data_source == "live":
                # mock_live: Need both brokers (real for data, mock for orders)
                if not self.mock_broker:
                    raise BrokerAPIError("Mock broker required for mock_live mode")
                real_result = self.real_broker.connect()
                mock_result = self.mock_broker.connect()
                logger.info(f"[{self.mode}] Connected to real broker: {real_result}, mock broker: {mock_result}")
                return real_result and mock_result

            elif self.account_type == "paper" and self.data_source == "live":
                # paper_live: Only real broker (IBKR paper account on port 4004)
                result = self.real_broker.connect()
                logger.info(f"[{self.mode}] Connected to real broker (IBKR paper account): {result}")
                return result

            elif self.account_type == "live" and self.data_source == "live":
                # live_live: Only real broker (production)
                result = self.real_broker.connect()
                logger.critical(f"[{self.mode}] Connected to LIVE broker - REAL MONEY AT RISK: {result}")
                return result

            else:
                raise BrokerAPIError(
                    f"Unsupported mode: account_type={self.account_type}, data_source={self.data_source}"
                )

        except Exception as e:
            logger.error(f"Connection error in mode {self.mode}: {e}")
            raise

    def disconnect(self) -> bool:
        """Disconnect from broker(s)."""
        try:
            if self.account_type == "mock" and self.data_source == "mock":
                return self.mock_broker.disconnect() if self.mock_broker else False

            elif self.account_type == "mock" and self.data_source == "live":
                if not self.mock_broker:
                    return False
                real_result = self.real_broker.disconnect()
                mock_result = self.mock_broker.disconnect()
                return real_result and mock_result

            elif self.account_type in ["paper", "live"]:
                # paper_live and live_live: Only real broker
                return self.real_broker.disconnect()

            return False

        except Exception as e:
            logger.error(f"Disconnection error in mode {self.mode}: {e}")
            return False

    def is_connected(self) -> bool:
        """Check connection status."""
        try:
            if self.account_type == "mock" and self.data_source == "mock":
                return self.mock_broker.is_connected() if self.mock_broker else False

            elif self.account_type == "mock" and self.data_source == "live":
                # Both must be connected for mock_live
                if not self.mock_broker:
                    return False
                return self.real_broker.is_connected() and self.mock_broker.is_connected()

            elif self.account_type in ["paper", "live"]:
                # paper_live and live_live: Only real broker
                return self.real_broker.is_connected()

            return False

        except Exception as e:
            logger.error(f"Connection check error in mode {self.mode}: {e}")
            return False

    # ORDER MANAGEMENT

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order with mode-based routing.

        - mock_mock: Send to mock broker with mock pricing
        - mock_live: Enrich with real pricing, then send to mock broker
        - paper_live: Send to real broker (IBKR paper account)
        - live_live: Send to real broker (production, CRITICAL)
        """
        try:
            if self.account_type == "live":
                # live_live: Real money at risk!
                logger.critical(f"⚠️ LIVE MODE ORDER: {order.get('instrument')} - REAL MONEY AT RISK!")
                return self.real_broker.place_order(order)

            elif self.account_type == "paper":
                # paper_live: IBKR paper account
                logger.info(f"[{self.mode}] Placing order on IBKR paper account: {order.get('instrument')}")
                return self.real_broker.place_order(order)

            elif self.account_type == "mock" and self.data_source == "live":
                # mock_live: Enrich order with live market pricing from real broker
                if not self.mock_broker:
                    raise BrokerAPIError("Mock broker required for mock_live mode")
                enriched_order = self._enrich_with_real_pricing(order)
                logger.info(f"[{self.mode}] Order enriched with real price: {enriched_order.get('price', 'N/A')}")
                return self.mock_broker.place_order(enriched_order)

            elif self.account_type == "mock" and self.data_source == "mock":
                # mock_mock: Use mock pricing (default behavior)
                if not self.mock_broker:
                    raise BrokerAPIError("Mock broker required for mock_mock mode")
                return self.mock_broker.place_order(order)

            else:
                raise BrokerAPIError(
                    f"Unsupported mode: account_type={self.account_type}, data_source={self.data_source}"
                )

        except Exception as e:
            logger.error(f"Error placing order in mode {self.mode}: {e}")
            raise

    def _enrich_with_real_pricing(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch live market price from real broker and add to order.

        This enables mock_live mode: testing with real market data without risking real money.
        
        CRITICAL: This MUST succeed in mock_live mode, as Mock broker has no fallback pricing.
        """
        try:
            symbol = order.get('instrument')
            instrument_type = order.get('instrument_type', 'STOCK')
            order_side = order.get('side', 'BUY')

            # Get live market price from real broker
            real_price = self.get_market_price(symbol, instrument_type)

            # Add price to order (mock broker will use this)
            enriched_order = order.copy()
            enriched_order['price'] = real_price
            enriched_order['_price_source'] = 'real_broker'

            logger.info(
                f"📈 [{self.mode}] Enriched {order_side} {symbol} order: "
                f"price=${real_price:.2f} (from real broker), "
                f"quantity={order.get('quantity', 'N/A')}"
            )
            return enriched_order

        except Exception as e:
            logger.critical(
                f"❌ CRITICAL: Failed to enrich {order.get('instrument')} order with real pricing in {self.mode} mode: {e}. "
                f"Cannot proceed - Mock broker requires a price and has no fallback."
            )
            raise BrokerAPIError(
                f"Price enrichment failed for {order.get('instrument')} in {self.mode} mode: {str(e)}. "
                f"Cannot execute order without live market price.",
                broker_name=self.real_broker.broker_name
            )

    def get_market_price(self, symbol: str, instrument_type: str) -> float:
        """
        Get current market price for an instrument.

        For mock_live and paper_live modes, this fetches live prices from the real broker.

        Args:
            symbol: Asset symbol (e.g., "AAPL", "EURUSD")
            instrument_type: Type of instrument ("STOCK", "FOREX", "CRYPTO", etc.)

        Returns:
            Current market price
        """
        if not hasattr(self.real_broker, 'get_market_price'):
            raise BrokerAPIError(f"Real broker {self.real_broker.broker_name} does not support get_market_price()")

        return self.real_broker.get_market_price(symbol, instrument_type)

    def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel order (routes to appropriate broker based on account_type)."""
        if self.account_type == "mock":
            # mock_mock or mock_live: Orders are in mock broker
            if not self.mock_broker:
                raise BrokerAPIError("Mock broker required for mock account types")
            return self.mock_broker.cancel_order(broker_order_id)
        else:
            # paper_live or live_live: Orders are in real broker
            return self.real_broker.cancel_order(broker_order_id)

    def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status (routes to appropriate broker based on account_type)."""
        if self.account_type == "mock":
            # mock_mock or mock_live: Orders are in mock broker
            if not self.mock_broker:
                raise BrokerAPIError("Mock broker required for mock account types")
            return self.mock_broker.get_order_status(broker_order_id)
        else:
            # paper_live or live_live: Orders are in real broker
            return self.real_broker.get_order_status(broker_order_id)

    # ACCOUNT DATA

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get account balance.

        - live_live, paper_live: From real broker
        - mock_mock, mock_live: From mock broker (simulated balances)
        """
        if self.account_type in ["live", "paper"]:
            return self.real_broker.get_account_balance(account_id)
        else:  # mock
            if not self.mock_broker:
                raise BrokerAPIError("Mock broker required for mock account types")
            return self.mock_broker.get_account_balance(account_id)

    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open positions (from appropriate broker based on account_type)."""
        if self.account_type in ["live", "paper"]:
            return self.real_broker.get_open_positions(account_id)
        else:  # mock
            if not self.mock_broker:
                raise BrokerAPIError("Mock broker required for mock account types")
            return self.mock_broker.get_open_positions(account_id)

    def get_margin_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Get margin info (from appropriate broker based on account_type)."""
        if self.account_type in ["live", "paper"]:
            return self.real_broker.get_margin_info(account_id)
        else:  # mock
            if not self.mock_broker:
                raise BrokerAPIError("Mock broker required for mock account types")
            return self.mock_broker.get_margin_info(account_id)

    def get_open_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders (from appropriate broker based on account_type)."""
        if self.account_type in ["live", "paper"]:
            return self.real_broker.get_open_orders(account_id)
        else:  # mock
            if not self.mock_broker:
                raise BrokerAPIError("Mock broker required for mock account types")
            return self.mock_broker.get_open_orders(account_id)

    # QUANTITY PRECISION

    def get_quantity_precision(self, symbol: str, instrument_type: str) -> int:
        """Get quantity precision (always from real broker for accuracy)."""
        return self.real_broker.get_quantity_precision(symbol, instrument_type)

    # UTILITY METHODS

    def get_mode(self) -> str:
        """Get current trading mode (computed from account_type_data_source)."""
        return self.mode
    
    def get_account_type(self) -> str:
        """Get account type (mock | paper | live)."""
        return self.account_type
    
    def get_data_source(self) -> str:
        """Get data source (mock | live)."""
        return self.data_source

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"BrokerModeAdapter(mode={self.mode}, account={self.account_id}, "
            f"account_type={self.account_type}, data_source={self.data_source}, "
            f"real={self.real_broker.broker_name}, "
            f"mock={self.mock_broker.broker_name if self.mock_broker else 'None'})"
        )
