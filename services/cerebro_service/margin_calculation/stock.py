"""
Stock & ETF Margin Calculator

Handles margin calculations for stocks and ETFs using broker data.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import BaseMarginCalculator, PriceFetchError, MarginFetchError


class StockMarginCalculator(BaseMarginCalculator):
    """
    Margin calculator for stocks and ETFs

    Fetches real-time prices and margin requirements from broker.
    Uses Reg T margin (25%) or broker-specific margin rates.
    """

    def fetch_current_price(self, ticker: str, signal: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Fetch current stock price from broker

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'SPY')
            signal: Optional signal dict (may contain fallback price as 'signal_price')

        Returns:
            Dict with price information:
            {
                'price': float,          # Current market price
                'bid': float,            # Bid price
                'ask': float,            # Ask price
                'timestamp': datetime    # Price timestamp
            }

        Raises:
            PriceFetchError: If price cannot be fetched
        """
        try:
            # Attempt to get ticker price from broker
            # Different brokers have different methods
            if hasattr(self.broker, 'get_ticker_price'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                price_data = self.broker.get_ticker_price(ticker, signal_price=signal_price)

                # Handle different response formats
                if isinstance(price_data, dict):
                    # Broker returned structured data
                    return {
                        'price': price_data.get('last', price_data.get('price', 0)),
                        'bid': price_data.get('bid', 0),
                        'ask': price_data.get('ask', 0),
                        'timestamp': price_data.get('timestamp', datetime.utcnow())
                    }
                elif isinstance(price_data, (int, float)):
                    # Broker returned just a price
                    return {
                        'price': float(price_data),
                        'bid': 0,
                        'ask': 0,
                        'timestamp': datetime.utcnow()
                    }
                else:
                    raise PriceFetchError(f"Unexpected price data format for {ticker}: {type(price_data)}")

            elif hasattr(self.broker, 'get_market_data'):
                # Alternative method name
                market_data = self.broker.get_market_data(ticker)
                return {
                    'price': market_data.get('last_price', market_data.get('close', 0)),
                    'bid': market_data.get('bid', 0),
                    'ask': market_data.get('ask', 0),
                    'timestamp': market_data.get('timestamp', datetime.utcnow())
                }

            else:
                raise PriceFetchError(
                    f"Broker {self.broker.__class__.__name__} does not support price fetching. "
                    f"Missing 'get_ticker_price' or 'get_market_data' method."
                )

        except PriceFetchError:
            raise
        except Exception as e:
            self.logger.error(f"Error fetching price for {ticker}: {e}", exc_info=True)
            raise PriceFetchError(f"Failed to fetch price for {ticker}: {str(e)}")

    def fetch_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Fetch margin requirement for stock from broker

        Args:
            ticker: Stock ticker symbol
            quantity: Number of shares
            price: Price per share

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
                        instrument_type='STOCK'
                    )

                    return {
                        'initial_margin': margin_data.get('initial_margin', notional_value * 0.25),
                        'maintenance_margin': margin_data.get('maintenance_margin', notional_value * 0.25),
                        'margin_pct': margin_data.get('margin_pct', 25.0),
                        'calculation_method': margin_data.get('method', 'Broker-provided margin')
                    }
                except Exception as e:
                    self.logger.warning(f"Broker margin fetch failed, using fallback: {e}")
                    # Fall through to fallback calculation

            # Fallback: Use standard Reg T margin (25%)
            margin_pct = 0.25
            initial_margin = notional_value * margin_pct

            self.logger.info(f"Using fallback Reg T margin: 25% of ${notional_value:.2f} = ${initial_margin:.2f}")

            return {
                'initial_margin': initial_margin,
                'maintenance_margin': initial_margin,  # Simplified: same as initial
                'margin_pct': 25.0,
                'calculation_method': 'Reg T Margin (25% of stock value - fallback)'
            }

        except Exception as e:
            self.logger.error(f"Error calculating margin for {ticker}: {e}", exc_info=True)
            raise MarginFetchError(f"Failed to calculate margin for {ticker}: {str(e)}")

    def validate_ticker(self, ticker: str) -> bool:
        """
        Validate that ticker is a valid stock/ETF

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if valid, False otherwise
        """
        # Check if broker has validation method
        if hasattr(self.broker, 'validate_instrument'):
            try:
                return self.broker.validate_instrument(ticker, 'STOCK')
            except:
                pass

        # Basic validation: ticker should be alphanumeric
        if not ticker or not ticker.replace('.', '').replace('-', '').isalnum():
            return False

        # Length check (most stock tickers are 1-5 characters)
        if len(ticker) > 10:
            return False

        return True
