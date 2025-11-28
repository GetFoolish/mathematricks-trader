"""
Futures Margin Calculator

Handles margin calculations for futures contracts using broker data.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import BaseMarginCalculator, PriceFetchError, MarginFetchError


class FutureMarginCalculator(BaseMarginCalculator):
    """
    Margin calculator for futures contracts

    Futures margin is fundamentally different from stocks:
    - NOT percentage-based
    - Fixed per-contract margin requirement
    - Set by exchange/clearinghouse
    - Varies by contract and market conditions

    Examples:
    - ES (E-mini S&P 500): ~$12,000/contract initial margin
    - CL (Crude Oil): ~$5,000/contract
    - GC (Gold): ~$10,000/contract

    IMPORTANT: MUST get margin from broker - no fallback calculation possible
    """

    def fetch_current_price(self, ticker: str, signal: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Fetch current futures price from broker

        Args:
            ticker: Futures symbol (e.g., 'ESZ3' = E-mini S&P Dec 2023)
            signal: Optional signal dict (may contain fallback price as 'signal_price')

        Returns:
            Dict with price information:
            {
                'price': float,          # Current settlement/mark price
                'bid': float,            # Bid price
                'ask': float,            # Ask price
                'timestamp': datetime    # Price timestamp
            }

        Raises:
            PriceFetchError: If price cannot be fetched
        """
        try:
            if hasattr(self.broker, 'get_futures_price'):
                # Pass signal_price if available for fallback
                signal_price = signal.get('signal_price') if signal else None
                price_data = self.broker.get_futures_price(ticker, signal_price=signal_price)

                if isinstance(price_data, dict):
                    return {
                        'price': price_data.get('last', price_data.get('settlement', price_data.get('price', 0))),
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
                market_data = self.broker.get_market_data(ticker, instrument_type='FUTURE')
                return {
                    'price': market_data.get('last_price', market_data.get('settlement', 0)),
                    'bid': market_data.get('bid', 0),
                    'ask': market_data.get('ask', 0),
                    'timestamp': market_data.get('timestamp', datetime.utcnow())
                }

            raise PriceFetchError(
                f"Broker {self.broker.__class__.__name__} does not support futures pricing. "
                f"Missing 'get_futures_price' or 'get_market_data' method."
            )

        except PriceFetchError:
            raise
        except Exception as e:
            self.logger.error(f"Error fetching futures price for {ticker}: {e}", exc_info=True)
            raise PriceFetchError(f"Failed to fetch futures price for {ticker}: {str(e)}")

    def fetch_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Fetch margin requirement for futures from broker

        Futures margin is PER CONTRACT, not percentage-based.

        Key differences from stocks:
        - Initial margin: Fixed $ per contract (e.g., $12,000 for ES)
        - Maintenance margin: Lower threshold (e.g., $10,000 for ES)
        - Notional value calculation: quantity × price × contract_multiplier

        Args:
            ticker: Futures symbol
            quantity: Number of contracts
            price: Price per contract

        Returns:
            Dict with margin information:
            {
                'initial_margin': float,         # Total initial margin = per_contract × quantity
                'maintenance_margin': float,     # Total maintenance margin
                'margin_per_contract': float,    # Exchange margin per contract
                'contract_multiplier': float,    # Point value (e.g., $50 for ES)
                'calculation_method': str
            }

        Raises:
            MarginFetchError: If margin cannot be fetched from broker
        """
        try:
            if hasattr(self.broker, 'get_margin_requirement'):
                margin_data = self.broker.get_margin_requirement(
                    ticker=ticker,
                    quantity=quantity,
                    price=price,
                    instrument_type='FUTURE'
                )

                # Futures margin is per-contract based
                margin_per_contract = margin_data.get('margin_per_contract', 0)
                num_contracts = abs(quantity)

                return {
                    'initial_margin': margin_data.get('initial_margin', margin_per_contract * num_contracts),
                    'maintenance_margin': margin_data.get('maintenance_margin', margin_per_contract * num_contracts * 0.8),
                    'margin_per_contract': margin_per_contract,
                    'contract_multiplier': margin_data.get('contract_multiplier', 1),
                    'margin_pct': None,  # Not applicable for futures
                    'calculation_method': margin_data.get('method', 'Broker-provided futures margin (per-contract)')
                }

            # For futures, we CANNOT use a fallback - margin varies too much by contract
            raise MarginFetchError(
                f"Broker {self.broker.__class__.__name__} does not support futures margin calculation. "
                f"Futures require broker-specific margin data (per-contract margins vary by exchange)."
            )

        except Exception as e:
            self.logger.error(f"Error getting futures margin for {ticker}: {e}", exc_info=True)
            raise MarginFetchError(f"Failed to get futures margin for {ticker}: {str(e)}")

    def get_contract_specifications(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch contract specifications from broker

        Args:
            ticker: Futures symbol

        Returns:
            Dict with contract specs:
            {
                'contract_size': float,        # Size of 1 contract
                'tick_size': float,            # Minimum price movement
                'point_value': float,          # $ value per point
                'expiration': str,             # Expiration date
                'underlying': str              # Underlying asset
            }

        Raises:
            PriceFetchError: If specs cannot be fetched
        """
        try:
            if hasattr(self.broker, 'get_contract_specifications'):
                return self.broker.get_contract_specifications(ticker)

            # Basic info extraction from ticker (limited)
            self.logger.warning(f"Broker does not provide contract specifications for {ticker}")
            return {
                'contract_size': None,
                'tick_size': None,
                'point_value': None,
                'expiration': None,
                'underlying': ticker[:2] if len(ticker) >= 2 else ticker  # ES -> ES
            }

        except Exception as e:
            self.logger.error(f"Error fetching contract specs for {ticker}: {e}", exc_info=True)
            raise PriceFetchError(f"Failed to fetch contract specs for {ticker}: {str(e)}")

    def validate_ticker(self, ticker: str) -> bool:
        """
        Validate that ticker is a valid futures contract

        Args:
            ticker: Futures ticker symbol

        Returns:
            True if valid, False otherwise
        """
        # Check if broker has validation method
        if hasattr(self.broker, 'validate_instrument'):
            try:
                return self.broker.validate_instrument(ticker, 'FUTURE')
            except:
                pass

        # Basic validation: futures tickers typically have format like ESZ3, CLF4, etc.
        # Usually 2-4 letters + month code + year digit
        if not ticker or len(ticker) < 3:
            return False

        # Allow alphanumeric with common separators
        if not ticker.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            return False

        return True
