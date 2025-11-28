"""
Broker Adapter for Cerebro Service

Provides broker-like interface for margin calculations.
Currently uses signal data and fallback calculations.
TODO: Integrate with real broker APIs for live pricing.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger('cerebro.broker_adapter')


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

    def __init__(self, broker_name: str = "IBKR"):
        """
        Initialize broker adapter

        Args:
            broker_name: Name of broker (for logging)
        """
        self.broker_name = broker_name
        logger.info(f"Initialized CerebroBrokerAdapter for {broker_name}")

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
        instrument_type: str
    ) -> Dict[str, Any]:
        """
        Get margin requirement for a trade.

        Current: Returns fallback calculations
        TODO: Fetch actual margin from broker

        Args:
            ticker: Instrument symbol
            quantity: Trade quantity
            price: Trade price
            instrument_type: STOCK, FOREX, OPTION, FUTURE, CRYPTO

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
            # Cannot provide fallback for futures - too variable
            raise ValueError(
                f"Cannot calculate futures margin without broker data. "
                f"Margin varies by contract and must be fetched from broker."
            )

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
