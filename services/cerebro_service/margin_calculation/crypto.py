"""
Crypto Margin Calculator

Handles margin calculations for cryptocurrency trading using broker/exchange data.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import BaseMarginCalculator, PriceFetchError, MarginFetchError


class CryptoMarginCalculator(BaseMarginCalculator):
    """
    Margin calculator for cryptocurrency

    Key considerations:
    - Exchange-specific pricing (Coinbase, Binance, etc. may differ)
    - Margin varies by exchange (2x, 3x, 5x, 10x leverage)
    - Some exchanges only offer spot trading (no margin)
    - Taker/maker fees can be significant
    - 24/7 markets with high volatility

    Default fallback: 50% margin (2x leverage) for margin accounts
    Spot trading: 100% cash required (no margin)
    """

    def fetch_current_price(self, ticker: str, signal: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Fetch current crypto price from broker/exchange

        Args:
            ticker: Crypto symbol (e.g., 'BTC', 'BTCUSD', 'BTC-USD')
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
            # Normalize ticker - remove common separators
            normalized_ticker = ticker.replace('-', '').replace('_', '').replace('/', '').upper()

            # Try crypto-specific method first
            if hasattr(self.broker, 'get_crypto_price'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                price_data = self.broker.get_crypto_price(normalized_ticker, signal_price=signal_price)

                if isinstance(price_data, dict):
                    return {
                        'price': price_data.get('last', price_data.get('price', 0)),
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

            # Try generic ticker price method
            elif hasattr(self.broker, 'get_ticker_price'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                price_data = self.broker.get_ticker_price(normalized_ticker, signal_price=signal_price)

                if isinstance(price_data, dict):
                    return {
                        'price': price_data.get('last', price_data.get('price', 0)),
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

            # Try generic market data method
            elif hasattr(self.broker, 'get_market_data'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                market_data = self.broker.get_market_data(normalized_ticker, instrument_type='CRYPTO', signal_price=signal_price)
                return {
                    'price': market_data.get('last_price', market_data.get('price', 0)),
                    'bid': market_data.get('bid', 0),
                    'ask': market_data.get('ask', 0),
                    'timestamp': market_data.get('timestamp', datetime.utcnow())
                }

            raise PriceFetchError(
                f"Broker {self.broker.__class__.__name__} does not support crypto pricing. "
                f"Missing 'get_crypto_price', 'get_ticker_price', or 'get_market_data' method."
            )

        except PriceFetchError:
            raise
        except Exception as e:
            self.logger.error(f"Error fetching crypto price for {ticker}: {e}", exc_info=True)
            raise PriceFetchError(f"Failed to fetch crypto price for {ticker}: {str(e)}")

    def fetch_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Fetch margin requirement for crypto from broker/exchange

        Crypto margin varies significantly:
        - Spot trading: 100% cash required (no leverage)
        - Margin trading: 50% (2x), 33% (3x), 20% (5x), 10% (10x) depending on exchange
        - Exchange risk limits may apply for large positions

        Args:
            ticker: Crypto symbol
            quantity: Amount of crypto
            price: Price per unit

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

            # Try to get margin from broker/exchange
            if hasattr(self.broker, 'get_margin_requirement'):
                try:
                    margin_data = self.broker.get_margin_requirement(
                        ticker=ticker,
                        quantity=quantity,
                        price=price,
                        instrument_type='CRYPTO'
                    )

                    return {
                        'initial_margin': margin_data.get('initial_margin', notional_value * 0.5),
                        'maintenance_margin': margin_data.get('maintenance_margin', notional_value * 0.5),
                        'margin_pct': margin_data.get('margin_pct', 50.0),
                        'calculation_method': margin_data.get('method', 'Exchange-provided margin')
                    }
                except Exception as e:
                    self.logger.warning(f"Exchange margin fetch failed, using fallback: {e}")
                    # Fall through to fallback calculation

            # Check if exchange supports margin trading
            if hasattr(self.broker, 'supports_margin_trading'):
                try:
                    if not self.broker.supports_margin_trading(ticker):
                        # Spot trading only - 100% cash required
                        self.logger.info(f"Exchange does not support margin trading for {ticker} - using spot (100%)")
                        return {
                            'initial_margin': notional_value,
                            'maintenance_margin': notional_value,
                            'margin_pct': 100.0,
                            'calculation_method': 'Spot trading (100% cash - no leverage)'
                        }
                except Exception as e:
                    self.logger.warning(f"Failed to check margin support: {e}")

            # Fallback: Conservative 50% margin (2x leverage)
            # This is common for many crypto margin accounts
            margin_pct = 0.5
            initial_margin = notional_value * margin_pct

            self.logger.info(
                f"Using fallback crypto margin: 50% of ${notional_value:.2f} = ${initial_margin:.2f} "
                f"(2x leverage)"
            )

            return {
                'initial_margin': initial_margin,
                'maintenance_margin': initial_margin,  # Simplified: same as initial
                'margin_pct': 50.0,
                'calculation_method': 'Conservative crypto margin (50% - 2x leverage fallback)'
            }

        except Exception as e:
            self.logger.error(f"Error calculating crypto margin for {ticker}: {e}", exc_info=True)
            raise MarginFetchError(f"Failed to calculate crypto margin for {ticker}: {str(e)}")

    def get_price_for_side(self, price_data: Dict[str, float], action: str) -> float:
        """
        Get appropriate price based on trade direction

        For crypto with significant spreads:
        - BUY: use ASK price (higher)
        - SELL: use BID price (lower)

        Args:
            price_data: Price data from fetch_current_price()
            action: 'BUY' or 'SELL'

        Returns:
            Appropriate price for the trade side
        """
        action = action.upper()

        if action == 'BUY':
            # Buying: pay the ASK price
            ask = price_data.get('ask', 0)
            if ask > 0:
                return ask
            # Fallback to mid or last price
            return price_data.get('price', 0)

        elif action == 'SELL':
            # Selling: receive the BID price
            bid = price_data.get('bid', 0)
            if bid > 0:
                return bid
            # Fallback to mid or last price
            return price_data.get('price', 0)

        # Default: mid price
        return price_data.get('price', 0)

    def validate_ticker(self, ticker: str) -> bool:
        """
        Validate that ticker is a valid crypto symbol

        Args:
            ticker: Crypto ticker symbol

        Returns:
            True if valid, False otherwise
        """
        # Check if broker has validation method
        if hasattr(self.broker, 'validate_instrument'):
            try:
                return self.broker.validate_instrument(ticker, 'CRYPTO')
            except:
                pass

        # Basic validation
        if not ticker:
            return False

        # Remove common separators
        normalized = ticker.replace('-', '').replace('_', '').replace('/', '')

        # Should be alphanumeric after normalization
        if not normalized.isalnum():
            return False

        # Length check (most crypto symbols are 3-10 characters)
        # BTC, ETH, BTCUSD, ETHUSD, etc.
        if len(normalized) < 2 or len(normalized) > 15:
            return False

        return True
