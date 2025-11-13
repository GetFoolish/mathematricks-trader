"""
Margin Calculator Factory

Selects the appropriate margin calculator based on instrument type.
"""

import logging
from typing import Dict, Any
from .base import BaseMarginCalculator
from .stock import StockMarginCalculator
from .forex import ForexMarginCalculator
from .option import OptionMarginCalculator
from .future import FutureMarginCalculator
from .crypto import CryptoMarginCalculator

logger = logging.getLogger('cerebro.margin_factory')


class MarginCalculatorFactory:
    """
    Factory for creating instrument-specific margin calculators

    Usage:
        signal = {'instrument_type': 'STOCK', 'ticker': 'AAPL', ...}
        calculator = MarginCalculatorFactory.create_calculator(signal, broker)
        result = calculator.calculate_position_size(signal, equity, capital)
    """

    # Mapping of instrument types to calculator classes
    CALCULATOR_MAP = {
        'STOCK': StockMarginCalculator,
        'ETF': StockMarginCalculator,      # ETFs use same logic as stocks
        'FOREX': ForexMarginCalculator,
        'OPTION': OptionMarginCalculator,
        'OPTIONS': OptionMarginCalculator,  # Accept plural form
        'FUTURE': FutureMarginCalculator,
        'FUTURES': FutureMarginCalculator,  # Accept plural form
        'CRYPTO': CryptoMarginCalculator,
        'CRYPTOCURRENCY': CryptoMarginCalculator  # Accept long form
    }

    @classmethod
    def create_calculator(
        cls,
        signal: Dict[str, Any],
        broker: Any
    ) -> BaseMarginCalculator:
        """
        Create appropriate margin calculator for the signal

        Args:
            signal: Trading signal dictionary (must contain 'instrument_type')
            broker: Broker instance for fetching prices and margins

        Returns:
            Appropriate margin calculator instance

        Raises:
            ValueError: If instrument_type is missing or invalid
        """
        # Step 1: Check if instrument_type exists
        instrument_type = signal.get('instrument_type')

        if not instrument_type:
            raise ValueError(
                "Signal is missing required field 'instrument_type'. "
                "Valid values: STOCK, ETF, FOREX, OPTION, FUTURE, CRYPTO"
            )

        # Step 2: Normalize instrument type (uppercase, strip whitespace)
        instrument_type = str(instrument_type).upper().strip()

        # Step 3: Check if it's a known instrument type
        if instrument_type not in cls.CALCULATOR_MAP:
            valid_types = ', '.join(sorted(set(cls.CALCULATOR_MAP.keys())))
            raise ValueError(
                f"Unknown instrument_type: '{instrument_type}'. "
                f"Valid types: {valid_types}"
            )

        # Step 4: Get the calculator class
        calculator_class = cls.CALCULATOR_MAP[instrument_type]

        # Step 5: Instantiate and return
        logger.info(f"Creating {calculator_class.__name__} for {instrument_type}")
        return calculator_class(broker=broker)

    @classmethod
    def get_supported_types(cls) -> list:
        """
        Get list of supported instrument types

        Returns:
            List of valid instrument_type values
        """
        return sorted(set(cls.CALCULATOR_MAP.keys()))

    @classmethod
    def is_supported(cls, instrument_type: str) -> bool:
        """
        Check if an instrument type is supported

        Args:
            instrument_type: Instrument type string

        Returns:
            True if supported, False otherwise
        """
        if not instrument_type:
            return False

        normalized = str(instrument_type).upper().strip()
        return normalized in cls.CALCULATOR_MAP
