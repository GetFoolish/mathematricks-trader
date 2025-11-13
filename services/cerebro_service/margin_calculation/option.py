"""
Options Margin Calculator

Handles margin calculations for options using broker data.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import BaseMarginCalculator, PriceFetchError, MarginFetchError


class OptionMarginCalculator(BaseMarginCalculator):
    """
    Margin calculator for options

    Options have complex margin requirements depending on:
    - Naked vs covered
    - Call vs put
    - Strategy (single, spread, etc.)

    IMPORTANT: Option price = premium, NOT strike price
    """

    def fetch_current_price(self, ticker: str, signal: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Fetch current option premium from broker

        Args:
            ticker: Option symbol
            signal: Optional signal dict (may contain fallback price as 'signal_price')

        Returns:
            Dict with price information (premium, not strike!)

        Raises:
            PriceFetchError: If premium cannot be fetched
        """
        try:
            if hasattr(self.broker, 'get_option_price'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                price_data = self.broker.get_option_price(ticker, signal_price=signal_price)

                if isinstance(price_data, dict):
                    return {
                        'price': price_data.get('premium', price_data.get('price', 0)),
                        'bid': price_data.get('bid', 0),
                        'ask': price_data.get('ask', 0),
                        'timestamp': price_data.get('timestamp', datetime.utcnow())
                    }
                elif isinstance(price_data, (int, float)):
                    return {
                        'price': float(price_data),
                        'bid': 0,
                        'ask': 0,
                        'timestamp': datetime.utcnow()
                    }

            raise PriceFetchError(
                f"Broker {self.broker.__class__.__name__} does not support option pricing. "
                f"Missing 'get_option_price' method."
            )

        except PriceFetchError:
            raise
        except Exception as e:
            self.logger.error(f"Error fetching option price for {ticker}: {e}", exc_info=True)
            raise PriceFetchError(f"Failed to fetch option price for {ticker}: {str(e)}")

    def fetch_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Fetch margin requirement for option from broker

        Options margin is complex and strategy-dependent.
        Broker MUST provide this - no simple fallback.

        Args:
            ticker: Option symbol
            quantity: Number of contracts
            price: Premium per contract

        Returns:
            Dict with margin information

        Raises:
            MarginFetchError: If margin cannot be fetched from broker
        """
        try:
            if hasattr(self.broker, 'get_margin_requirement'):
                margin_data = self.broker.get_margin_requirement(
                    ticker=ticker,
                    quantity=quantity,
                    price=price,
                    instrument_type='OPTION'
                )

                return {
                    'initial_margin': margin_data.get('initial_margin', 0),
                    'maintenance_margin': margin_data.get('maintenance_margin', 0),
                    'margin_pct': margin_data.get('margin_pct', 0),
                    'calculation_method': margin_data.get('method', 'Broker-provided option margin')
                }

            # For options, we CANNOT use a fallback - too complex
            raise MarginFetchError(
                f"Broker {self.broker.__class__.__name__} does not support option margin calculation. "
                f"Options require broker-specific margin computation."
            )

        except Exception as e:
            self.logger.error(f"Error getting option margin for {ticker}: {e}", exc_info=True)
            raise MarginFetchError(f"Failed to get option margin for {ticker}: {str(e)}")
