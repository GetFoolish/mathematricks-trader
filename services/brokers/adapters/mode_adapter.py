"""
BrokerModeAdapter - Hybrid adapter for 3-mode trading system

This adapter wraps real broker + mock broker instances to enable:
- paper_mock: Fake pricing + mock broker orders (fully simulated)
- paper_live: LIVE pricing from real broker + mock broker orders (safe testing with real market data)
- live: Live pricing + real broker orders (production trading)

The adapter routes method calls based on the mode field from trading_accounts collection.
"""
from typing import Dict, Any, List, Optional
from services.brokers.base import AbstractBroker
from services.brokers.exceptions import BrokerAPIError
import logging

logger = logging.getLogger(__name__)


class BrokerModeAdapter(AbstractBroker):
    """
    Adapter that wraps real broker + mock broker instances for mode-based routing.

    Modes:
    - paper_mock: All calls go to mock broker with fake pricing
    - paper_live: Pricing from real broker, orders to mock broker
    - live: All calls go to real broker
    """

    def __init__(self, real_broker: AbstractBroker, mock_broker: AbstractBroker, mode: str):
        """
        Initialize the adapter with both broker instances.

        Args:
            real_broker: Real broker instance (e.g., IBKRBroker)
            mock_broker: Mock broker instance
            mode: Trading mode - "paper_mock" | "paper_live" | "live"
        """
        # Create a combined config for the base class
        config = {
            "broker": f"{real_broker.broker_name}_Adapter",
            "account_id": real_broker.account_id or mock_broker.account_id,
            "mode": mode
        }
        super().__init__(config)

        self.real_broker = real_broker
        self.mock_broker = mock_broker
        self.mode = mode

        logger.info(f"BrokerModeAdapter initialized for account {self.account_id} in mode: {mode}")
        logger.info(f"  Real broker: {real_broker.broker_name}")
        logger.info(f"  Mock broker: {mock_broker.broker_name}")

    # CONNECTION MANAGEMENT

    def connect(self) -> bool:
        """
        Connect to appropriate broker(s) based on mode.

        - paper_mock: Connect only to mock
        - paper_live: Connect to both (need real for pricing)
        - live: Connect only to real
        """
        try:
            if self.mode == "paper_mock":
                result = self.mock_broker.connect()
                logger.info(f"[{self.mode}] Connected to mock broker: {result}")
                return result

            elif self.mode == "paper_live":
                # Connect to both brokers
                real_result = self.real_broker.connect()
                mock_result = self.mock_broker.connect()
                logger.info(f"[{self.mode}] Connected to real broker: {real_result}, mock broker: {mock_result}")
                return real_result and mock_result

            elif self.mode == "live":
                result = self.real_broker.connect()
                logger.info(f"[{self.mode}] Connected to real broker: {result}")
                return result

            else:
                logger.error(f"Invalid mode: {self.mode}")
                return False

        except Exception as e:
            logger.error(f"Connection error in mode {self.mode}: {e}")
            raise

    def disconnect(self) -> bool:
        """Disconnect from broker(s)."""
        try:
            if self.mode == "paper_mock":
                return self.mock_broker.disconnect()

            elif self.mode == "paper_live":
                real_result = self.real_broker.disconnect()
                mock_result = self.mock_broker.disconnect()
                return real_result and mock_result

            elif self.mode == "live":
                return self.real_broker.disconnect()

            return False

        except Exception as e:
            logger.error(f"Disconnection error in mode {self.mode}: {e}")
            return False

    def is_connected(self) -> bool:
        """Check connection status."""
        try:
            if self.mode == "paper_mock":
                return self.mock_broker.is_connected()

            elif self.mode == "paper_live":
                # Both must be connected for paper_live
                return self.real_broker.is_connected() and self.mock_broker.is_connected()

            elif self.mode == "live":
                return self.real_broker.is_connected()

            return False

        except Exception as e:
            logger.error(f"Connection check error in mode {self.mode}: {e}")
            return False

    # ORDER MANAGEMENT

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order with mode-based routing.

        - paper_mock: Send to mock broker with fake pricing
        - paper_live: Enrich with real pricing, then send to mock broker
        - live: Send directly to real broker
        """
        try:
            if self.mode == "live":
                logger.critical(f"⚠️ LIVE MODE ORDER: {order.get('instrument')} - Real money at risk!")
                return self.real_broker.place_order(order)

            elif self.mode == "paper_live":
                # Enrich order with live market pricing from real broker
                enriched_order = self._enrich_with_real_pricing(order)
                logger.info(f"[paper_live] Order enriched with real price: {enriched_order.get('price', 'N/A')}")
                return self.mock_broker.place_order(enriched_order)

            elif self.mode == "paper_mock":
                # Use mock pricing (default behavior)
                return self.mock_broker.place_order(order)

            else:
                raise BrokerAPIError(f"Invalid mode: {self.mode}")

        except Exception as e:
            logger.error(f"Error placing order in mode {self.mode}: {e}")
            raise

    def _enrich_with_real_pricing(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch live market price from real broker and add to order.

        This enables paper_live mode: testing with real market data without risking real money.
        
        CRITICAL: This MUST succeed in paper_live mode, as Mock broker has no fallback pricing.
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
                f"📈 [paper_live] Enriched {order_side} {symbol} order: "
                f"price=${real_price:.2f} (from real broker), "
                f"quantity={order.get('quantity', 'N/A')}"
            )
            return enriched_order

        except Exception as e:
            logger.critical(
                f"❌ CRITICAL: Failed to enrich {order.get('instrument')} order with real pricing in paper_live mode: {e}. "
                f"Cannot proceed - Mock broker requires a price and has no fallback."
            )
            raise BrokerAPIError(
                f"Price enrichment failed for {order.get('instrument')} in paper_live mode: {str(e)}. "
                f"Cannot execute order without live market price.",
                broker_name=self.real_broker.broker_name
            )

    def get_market_price(self, symbol: str, instrument_type: str) -> float:
        """
        Get current market price for an instrument.

        For paper_live mode, this fetches live prices from the real broker.

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
        """Cancel order (routes to appropriate broker)."""
        if self.mode == "live":
            return self.real_broker.cancel_order(broker_order_id)
        else:  # paper_mock or paper_live
            return self.mock_broker.cancel_order(broker_order_id)

    def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status (routes to appropriate broker)."""
        if self.mode == "live":
            return self.real_broker.get_order_status(broker_order_id)
        else:  # paper_mock or paper_live
            return self.mock_broker.get_order_status(broker_order_id)

    # ACCOUNT DATA

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get account balance.

        - live: From real broker
        - paper_mock/paper_live: From mock broker (simulated balances)
        """
        if self.mode == "live":
            return self.real_broker.get_account_balance(account_id)
        else:  # paper_mock or paper_live
            return self.mock_broker.get_account_balance(account_id)

    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open positions (from appropriate broker)."""
        if self.mode == "live":
            return self.real_broker.get_open_positions(account_id)
        else:  # paper_mock or paper_live
            return self.mock_broker.get_open_positions(account_id)

    def get_margin_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Get margin info (from appropriate broker)."""
        if self.mode == "live":
            return self.real_broker.get_margin_info(account_id)
        else:  # paper_mock or paper_live
            return self.mock_broker.get_margin_info(account_id)

    def get_open_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders (from appropriate broker)."""
        if self.mode == "live":
            return self.real_broker.get_open_orders(account_id)
        else:  # paper_mock or paper_live
            return self.mock_broker.get_open_orders(account_id)

    # QUANTITY PRECISION

    def get_quantity_precision(self, symbol: str, instrument_type: str) -> int:
        """Get quantity precision (always from real broker for accuracy)."""
        return self.real_broker.get_quantity_precision(symbol, instrument_type)

    # UTILITY METHODS

    def get_mode(self) -> str:
        """Get current trading mode."""
        return self.mode

    def __repr__(self) -> str:
        """String representation."""
        return f"BrokerModeAdapter(mode={self.mode}, account={self.account_id}, real={self.real_broker.broker_name}, mock={self.mock_broker.broker_name})"
