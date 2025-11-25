"""
Broker Adapter for Cerebro Service

Provides broker-like interface for margin calculations.
Uses AccountDataService to fetch real margin data from IBKR for futures.
"""

import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger('cerebro.broker_adapter')

# AccountDataService URL
ACCOUNT_DATA_SERVICE_URL = "http://localhost:8082"


class CerebroBrokerAdapter:
    """
    Adapter to provide broker-like interface for margin calculators.

    Current implementation (Phase 1):
    - Uses signal data for prices when available
    - Provides fallback margin calculations
    - Does NOT fetch live prices from broker

    Future implementation (Phase 2):
    - Integrate with AccountDataService API
    - Fetch real-time prices from broker
    - Get actual margin requirements from broker
    """

    def __init__(self, broker_name: str = "IBKR", account_id: str = "IBKR_PAPER", use_mock: bool = False):
        """
        Initialize broker adapter

        Args:
            broker_name: Name of broker (for logging)
            account_id: Account ID for margin queries
            use_mock: If True, use mock data instead of real broker connections
        """
        self.broker_name = broker_name
        self.account_id = account_id
        self.use_mock = use_mock
        mode_str = "MOCK MODE" if use_mock else "LIVE MODE"
        logger.info(f"Initialized CerebroBrokerAdapter for {broker_name} (account: {account_id}) - {mode_str}")

    # ========================================================================
    # STOCK/ETF PRICING
    # ========================================================================

    def get_ticker_price(self, ticker: str, signal_price: Optional[float] = None) -> Dict[str, float]:
        """
        Get stock/ETF price.

        Current: Uses signal price if provided
        TODO: Fetch from broker API

        Args:
            ticker: Stock ticker
            signal_price: Price from signal (fallback)

        Returns:
            Dict with price data
        """
        if signal_price and signal_price > 0:
            logger.debug(f"Using signal price for {ticker}: ${signal_price}")
            return {
                'price': signal_price,
                'last': signal_price,
                'bid': signal_price * 0.999,  # Approximate bid (0.1% below)
                'ask': signal_price * 1.001,  # Approximate ask (0.1% above)
                'timestamp': datetime.utcnow()
            }

        # If no signal price, we must reject
        raise ValueError(
            f"No price available for {ticker}. "
            f"Signal must include 'price' field, or broker integration must be completed."
        )

    # ========================================================================
    # FOREX PRICING
    # ========================================================================

    def get_forex_rate(self, ticker: str, signal_price: Optional[float] = None) -> Dict[str, float]:
        """
        Get forex pair rate.

        Current: Uses signal price if provided
        TODO: Fetch from broker API

        Args:
            ticker: Forex pair (e.g., 'AUDCAD')
            signal_price: Price from signal (fallback)

        Returns:
            Dict with rate data
        """
        if signal_price and signal_price > 0:
            # For forex, bid/ask spread is typically 0.0001-0.0005
            spread = signal_price * 0.0002  # 0.02% spread
            logger.debug(f"Using signal price for {ticker}: {signal_price}")
            return {
                'price': signal_price,
                'mid': signal_price,
                'bid': signal_price - spread / 2,
                'ask': signal_price + spread / 2,
                'timestamp': datetime.utcnow()
            }

        raise ValueError(
            f"No price available for forex pair {ticker}. "
            f"Signal must include 'price' field, or broker integration must be completed."
        )

    # ========================================================================
    # OPTIONS PRICING
    # ========================================================================

    def get_option_price(self, ticker: str, signal_price: Optional[float] = None) -> Dict[str, float]:
        """
        Get option premium.

        Current: Uses signal price if provided
        TODO: Fetch from broker API

        Args:
            ticker: Option symbol
            signal_price: Premium from signal (fallback)

        Returns:
            Dict with premium data
        """
        if signal_price and signal_price > 0:
            logger.debug(f"Using signal premium for {ticker}: ${signal_price}")
            return {
                'price': signal_price,
                'premium': signal_price,
                'bid': signal_price * 0.95,  # Approximate (5% spread for options)
                'ask': signal_price * 1.05,
                'timestamp': datetime.utcnow()
            }

        raise ValueError(
            f"No premium available for option {ticker}. "
            f"Signal must include 'price' field, or broker integration must be completed."
        )

    # ========================================================================
    # FUTURES PRICING
    # ========================================================================

    def get_futures_price(self, ticker: str, signal_price: Optional[float] = None) -> Dict[str, float]:
        """
        Get futures price.

        Current: Uses signal price if provided
        TODO: Fetch from broker API

        Args:
            ticker: Futures symbol
            signal_price: Price from signal (fallback)

        Returns:
            Dict with price data
        """
        if signal_price and signal_price > 0:
            logger.debug(f"Using signal price for {ticker}: {signal_price}")
            return {
                'price': signal_price,
                'settlement': signal_price,
                'last': signal_price,
                'bid': signal_price - 0.01,  # Approximate tick
                'ask': signal_price + 0.01,
                'timestamp': datetime.utcnow()
            }

        raise ValueError(
            f"No price available for futures {ticker}. "
            f"Signal must include 'price' field, or broker integration must be completed."
        )

    # ========================================================================
    # CRYPTO PRICING
    # ========================================================================

    def get_crypto_price(self, ticker: str, signal_price: Optional[float] = None) -> Dict[str, float]:
        """
        Get cryptocurrency price.

        Current: Uses signal price if provided
        TODO: Fetch from exchange API

        Args:
            ticker: Crypto symbol
            signal_price: Price from signal (fallback)

        Returns:
            Dict with price data
        """
        if signal_price and signal_price > 0:
            # Crypto spreads can be wider (0.1-0.5%)
            logger.debug(f"Using signal price for {ticker}: ${signal_price}")
            return {
                'price': signal_price,
                'last': signal_price,
                'bid': signal_price * 0.997,  # 0.3% spread
                'ask': signal_price * 1.003,
                'timestamp': datetime.utcnow()
            }

        raise ValueError(
            f"No price available for crypto {ticker}. "
            f"Signal must include 'price' field, or exchange integration must be completed."
        )

    # ========================================================================
    # MARGIN REQUIREMENTS
    # ========================================================================

    def get_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float,
        instrument_type: str,
        signal_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get margin requirement for a trade.

        For futures, queries AccountDataService which uses IBKR's whatIfOrder API.
        For other instruments, uses fallback calculations.

        Args:
            ticker: Instrument symbol
            quantity: Trade quantity
            price: Trade price
            instrument_type: STOCK, FOREX, OPTION, FUTURE, CRYPTO
            signal_data: Additional signal data (expiry, exchange, direction)

        Returns:
            Dict with margin info
        """
        notional_value = quantity * price
        instrument_type = instrument_type.upper()

        # Use standard margin rates based on instrument type
        if instrument_type == 'STOCK' or instrument_type == 'ETF':
            # Reg T margin: 25%
            margin = notional_value * 0.25
            return {
                'initial_margin': margin,
                'maintenance_margin': margin,
                'margin_pct': 25.0,
                'method': 'Reg T Margin (25% - fallback)'
            }

        elif instrument_type == 'FOREX':
            # 50:1 leverage = 2%
            margin = notional_value * 0.02
            return {
                'initial_margin': margin,
                'maintenance_margin': margin,
                'margin_pct': 2.0,
                'method': 'Forex Margin (50:1 leverage - fallback)'
            }

        elif instrument_type == 'CRYPTO':
            # Conservative 2x leverage = 50%
            margin = notional_value * 0.5
            return {
                'initial_margin': margin,
                'maintenance_margin': margin,
                'margin_pct': 50.0,
                'method': 'Crypto Margin (2x leverage - fallback)'
            }

        elif instrument_type == 'FUTURE':
            # In mock mode, use estimated margin; otherwise query IBKR
            if self.use_mock:
                # Use 10% initial margin estimate for mock mode (typical for Gold/Copper futures)
                margin = notional_value * 0.10
                logger.info(f"📋 MOCK MODE: Using estimated futures margin for {ticker}: ${margin:,.2f}")
                return {
                    'initial_margin': margin,
                    'maintenance_margin': margin * 0.75,
                    'margin_pct': 10.0,
                    'method': 'Futures Mock Margin (10% estimate)'
                }
            else:
                # Query actual margin from IBKR via AccountDataService
                return self._get_futures_margin_from_broker(ticker, quantity, signal_data)

        elif instrument_type == 'OPTION':
            # Cannot provide fallback for options - too complex
            raise ValueError(
                f"Cannot calculate options margin without broker data. "
                f"Options margin is strategy-dependent and must be fetched from broker."
            )

        else:
            # Unknown type - use conservative 25%
            margin = notional_value * 0.25
            return {
                'initial_margin': margin,
                'maintenance_margin': margin,
                'margin_pct': 25.0,
                'method': 'Conservative default (25%)'
            }

    def _get_futures_margin_from_broker(
        self,
        ticker: str,
        quantity: float,
        signal_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get actual futures margin from IBKR via AccountDataService.

        Args:
            ticker: Futures symbol (e.g., 'GC')
            quantity: Number of contracts
            signal_data: Signal data with expiry, exchange, direction

        Returns:
            Dict with margin info from broker

        Raises:
            ValueError: If margin cannot be fetched from broker
        """
        if not signal_data:
            raise ValueError(
                f"Cannot calculate futures margin without signal data. "
                f"Signal must include expiry and exchange fields."
            )

        expiry = signal_data.get('expiry')
        exchange = signal_data.get('exchange')
        direction = signal_data.get('direction', 'LONG')

        if not expiry:
            raise ValueError(
                f"Cannot calculate futures margin without expiry. "
                f"Signal must include 'expiry' field (e.g., '20250224')."
            )

        if not exchange:
            raise ValueError(
                f"Cannot calculate futures margin without exchange. "
                f"Signal must include 'exchange' field (e.g., 'COMEX')."
            )

        # Build margin preview request
        payload = {
            "instrument": ticker,
            "direction": direction,
            "quantity": quantity,
            "order_type": "MARKET",
            "instrument_type": "FUTURE",
            "expiry": expiry,
            "exchange": exchange
        }

        try:
            logger.info(f"Querying IBKR for futures margin: {ticker} {direction} {quantity} contracts")
            url = f"{ACCOUNT_DATA_SERVICE_URL}/api/v1/account/{self.account_id}/margin-preview"

            response = requests.post(url, json=payload, timeout=35)

            if response.status_code == 200:
                result = response.json()
                margin_impact = result.get('margin_impact', {})

                init_margin = margin_impact.get('init_margin_change', 0)
                maint_margin = margin_impact.get('maint_margin_change', 0)

                logger.info(f"✅ Futures margin from IBKR: Initial=${init_margin:,.2f}, Maintenance=${maint_margin:,.2f}")

                return {
                    'initial_margin': init_margin,
                    'maintenance_margin': maint_margin,
                    'margin_pct': 0,  # Not percentage-based for futures
                    'method': 'IBKR whatIfOrder (actual margin)',
                    'commission': margin_impact.get('commission', 0)
                }
            else:
                error_detail = response.json().get('detail', response.text)
                raise ValueError(f"Failed to get futures margin from IBKR: {error_detail}")

        except requests.exceptions.Timeout:
            raise ValueError(
                f"Timeout waiting for futures margin from IBKR. "
                f"Ensure TWS/Gateway is running and AccountDataService is available."
            )
        except requests.exceptions.ConnectionError:
            raise ValueError(
                f"Cannot connect to AccountDataService at {ACCOUNT_DATA_SERVICE_URL}. "
                f"Ensure the service is running."
            )
        except Exception as e:
            raise ValueError(f"Failed to get futures margin for {ticker}: {str(e)}")

    # ========================================================================
    # QUANTITY PRECISION
    # ========================================================================

    def get_quantity_precision(self, symbol: str, instrument_type: str) -> int:
        """
        Get the number of decimal places allowed for quantity.

        Current: Uses default precision map
        TODO: Query real broker for actual precision

        Args:
            symbol: Asset symbol (e.g., "AAPL", "EURUSD")
            instrument_type: Type of instrument

        Returns:
            int: Number of decimal places (0 for integers)
        """
        precision_map = {
            'STOCK': 0,      # Integer shares
            'ETF': 0,        # Integer shares
            'OPTION': 0,     # Integer contracts
            'FUTURE': 0,     # Integer contracts
            'FOREX': 0,      # Units (IBKR uses whole units)
            'CRYPTO': 8,     # Up to 8 decimal places for crypto
        }

        precision = precision_map.get(instrument_type.upper(), 0)
        logger.debug(f"Precision for {symbol} ({instrument_type}): {precision} decimals")
        return precision
