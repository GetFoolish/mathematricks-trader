"""
Forex Margin Calculator

Handles margin calculations for forex pairs using broker data.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import BaseMarginCalculator, PriceFetchError, MarginFetchError


class ForexMarginCalculator(BaseMarginCalculator):
    """
    Margin calculator for forex pairs

    Fetches real-time forex rates and margin requirements from broker.
    Handles bid/ask spreads and different lot sizes.
    Typically uses 2% margin (50:1 leverage) or broker-specific rates.
    """

    def fetch_current_price(self, ticker: str, signal: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Fetch current forex rate from broker

        Args:
            ticker: Forex pair (e.g., 'AUDCAD', 'EURUSD')
            signal: Optional signal dict (may contain fallback price as 'signal_price')

        Returns:
            Dict with price information:
            {
                'price': float,          # Mid price (bid+ask)/2
                'bid': float,            # Bid price (for SELL)
                'ask': float,            # Ask price (for BUY)
                'timestamp': datetime    # Price timestamp
            }

        Raises:
            PriceFetchError: If price cannot be fetched
        """
        try:
            # Normalize ticker format (remove slashes, etc.)
            normalized_ticker = ticker.replace('/', '').replace('_', '').upper()

            # Attempt to get forex rate from broker
            if hasattr(self.broker, 'get_forex_rate'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                rate_data = self.broker.get_forex_rate(normalized_ticker, signal_price=signal_price)

                if isinstance(rate_data, dict):
                    bid = rate_data.get('bid', 0)
                    ask = rate_data.get('ask', 0)
                    mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else rate_data.get('price', 0)

                    return {
                        'price': mid,
                        'bid': bid,
                        'ask': ask,
                        'timestamp': rate_data.get('timestamp', datetime.utcnow())
                    }
                elif isinstance(rate_data, (int, float)):
                    # Single price returned, assume it's mid
                    return {
                        'price': float(rate_data),
                        'bid': 0,
                        'ask': 0,
                        'timestamp': datetime.utcnow()
                    }

            elif hasattr(self.broker, 'get_ticker_price'):
                # Fallback to generic price method
                price_data = self.broker.get_ticker_price(normalized_ticker)

                if isinstance(price_data, dict):
                    bid = price_data.get('bid', 0)
                    ask = price_data.get('ask', 0)
                    price = price_data.get('last', price_data.get('price', 0))

                    # If no bid/ask, use price for both
                    if bid == 0 and ask == 0 and price > 0:
                        # Estimate spread (typically 0.01% for major pairs)
                        spread = price * 0.0001
                        bid = price - spread / 2
                        ask = price + spread / 2

                    mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else price

                    return {
                        'price': mid,
                        'bid': bid,
                        'ask': ask,
                        'timestamp': price_data.get('timestamp', datetime.utcnow())
                    }
                elif isinstance(price_data, (int, float)):
                    return {
                        'price': float(price_data),
                        'bid': 0,
                        'ask': 0,
                        'timestamp': datetime.utcnow()
                    }

            else:
                raise PriceFetchError(
                    f"Broker {self.broker.__class__.__name__} does not support forex rate fetching. "
                    f"Missing 'get_forex_rate' or 'get_ticker_price' method."
                )

        except PriceFetchError:
            raise
        except Exception as e:
            self.logger.error(f"Error fetching forex rate for {ticker}: {e}", exc_info=True)
            raise PriceFetchError(f"Failed to fetch forex rate for {ticker}: {str(e)}")

    def fetch_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Fetch margin requirement for forex from broker

        Args:
            ticker: Forex pair
            quantity: Number of units (e.g., 100,000 for 1 standard lot)
            price: Exchange rate

        Returns:
            Dict with margin information:
            {
                'initial_margin': float,     # Initial margin required
                'maintenance_margin': float, # Maintenance margin
                'margin_pct': float,         # Margin as percentage
                'calculation_method': str    # Description of calculation
            }

        Raises:
            MarginFetchError: If margin cannot be fetched
        """
        try:
            notional_value = quantity * price

            # Try to get margin from broker
            if hasattr(self.broker, 'get_margin_requirement'):
                try:
                    margin_data = self.broker.get_margin_requirement(
                        ticker=ticker,
                        quantity=quantity,
                        price=price,
                        instrument_type='FOREX'
                    )

                    return {
                        'initial_margin': margin_data.get('initial_margin', notional_value * 0.02),
                        'maintenance_margin': margin_data.get('maintenance_margin', notional_value * 0.02),
                        'margin_pct': margin_data.get('margin_pct', 2.0),
                        'calculation_method': margin_data.get('method', 'Broker-provided forex margin')
                    }
                except Exception as e:
                    self.logger.warning(f"Broker margin fetch failed, using fallback: {e}")
                    # Fall through to fallback calculation

            # Fallback: Use standard forex margin (2% = 50:1 leverage)
            margin_pct = 0.02
            initial_margin = notional_value * margin_pct

            # Calculate lot size for logging
            lot_size = quantity / 100000  # Standard lot = 100,000 units

            self.logger.info(
                f"Using fallback forex margin: 2% (50:1 leverage) of ${notional_value:.2f} = ${initial_margin:.2f} "
                f"(~{lot_size:.2f} lots)"
            )

            return {
                'initial_margin': initial_margin,
                'maintenance_margin': initial_margin * 0.5,  # Maintenance typically 50% of initial
                'margin_pct': 2.0,
                'calculation_method': 'Forex Margin (50:1 leverage - fallback)'
            }

        except Exception as e:
            self.logger.error(f"Error calculating margin for {ticker}: {e}", exc_info=True)
            raise MarginFetchError(f"Failed to calculate margin for {ticker}: {str(e)}")

    def get_price_for_side(self, price_data: Dict[str, float], action: str) -> float:
        """
        Get appropriate price based on trade side (BUY/SELL)

        For forex, we use:
        - ASK price for BUY orders (we buy at seller's ask)
        - BID price for SELL orders (we sell at buyer's bid)

        Args:
            price_data: Dict from fetch_current_price()
            action: 'BUY' or 'SELL'

        Returns:
            Appropriate price for the trade side
        """
        bid = price_data.get('bid', 0)
        ask = price_data.get('ask', 0)
        mid = price_data.get('price', 0)

        if action.upper() == 'BUY':
            # Use ASK if available, otherwise mid
            return ask if ask > 0 else mid
        else:  # SELL
            # Use BID if available, otherwise mid
            return bid if bid > 0 else mid

    def calculate_position_size(
        self,
        signal: Dict[str, Any],
        account_equity: float,
        position_capital: float
    ) -> Dict[str, Any]:
        """
        Override to handle forex-specific bid/ask pricing

        Uses ASK for BUY, BID for SELL when available
        """
        # First, call parent method to get base calculation
        result = super().calculate_position_size(signal, account_equity, position_capital)

        # Adjust for forex-specific pricing if bid/ask available
        action = signal.get('action', 'BUY').upper()
        broker_price = result['broker_price']

        if broker_price.get('bid', 0) > 0 and broker_price.get('ask', 0) > 0:
            side_specific_price = self.get_price_for_side(broker_price, action)
            spread = broker_price['ask'] - broker_price['bid']
            spread_pct = (spread / broker_price['price'] * 100) if broker_price['price'] > 0 else 0

            self.logger.info(
                f"Forex spread: ${spread:.5f} ({spread_pct:.3f}%) | "
                f"Using {'ASK' if action == 'BUY' else 'BID'} price: ${side_specific_price:.5f}"
            )

            # Add forex-specific info to result
            result['forex_info'] = {
                'bid': broker_price['bid'],
                'ask': broker_price['ask'],
                'spread': spread,
                'spread_pct': spread_pct,
                'price_used_for_side': side_specific_price
            }

        return result
