"""
Base Margin Calculator

Abstract base class for all asset-specific margin calculators.
All margin calculators must fetch price and margin from broker.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PriceFetchError(Exception):
    """Raised when price cannot be fetched from broker"""
    pass


class MarginFetchError(Exception):
    """Raised when margin requirement cannot be fetched from broker"""
    pass


class BaseMarginCalculator(ABC):
    """
    Base class for asset-specific margin calculators.

    Key principles:
    - Broker is single source of truth for prices and margin
    - Fail-safe: raise exception if broker fetch fails
    - Support both MARKET and LIMIT orders
    - For LIMIT orders: use worse-case price for margin calculation
    """

    def __init__(self, broker):
        """
        Initialize calculator with broker connection

        Args:
            broker: Broker instance (e.g., IBKRBroker, ZerodhaBroker)
        """
        self.broker = broker
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def fetch_current_price(self, ticker: str, signal: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Fetch current price from broker

        Args:
            ticker: Instrument ticker/symbol
            signal: Optional signal dict (may contain fallback price as 'signal_price')

        Returns:
            Dict with price information:
            {
                'price': float,          # Current market price
                'bid': float,            # Bid price (if applicable)
                'ask': float,            # Ask price (if applicable)
                'timestamp': datetime    # Price timestamp
            }

        Raises:
            PriceFetchError: If price cannot be fetched
        """
        pass

    @abstractmethod
    def fetch_margin_requirement(
        self,
        ticker: str,
        quantity: float,
        price: float
    ) -> Dict[str, Any]:
        """
        Fetch margin requirement from broker

        Args:
            ticker: Instrument ticker/symbol
            quantity: Number of units/shares/contracts
            price: Price for margin calculation

        Returns:
            Dict with margin information:
            {
                'initial_margin': float,     # Initial margin required
                'maintenance_margin': float, # Maintenance margin
                'margin_pct': float,         # Margin as percentage (if applicable)
                'calculation_method': str    # Description of calculation
            }

        Raises:
            MarginFetchError: If margin cannot be fetched
        """
        pass

    def calculate_position_size(
        self,
        signal: Dict[str, Any],
        account_equity: float,
        position_capital: float
    ) -> Dict[str, Any]:
        """
        Calculate position size based on broker data

        Args:
            signal: Signal dictionary with ticker, action, order_type, etc.
            account_equity: Current account equity
            position_capital: Capital allocated for this position

        Returns:
            Dict with position sizing information:
            {
                'quantity': float,              # Calculated quantity
                'price_used': float,            # Price used for calculations
                'notional_value': float,        # Total position value
                'initial_margin': float,        # Required initial margin
                'margin_pct': float,            # Margin percentage
                'calculation_method': str,      # How it was calculated
                'broker_price': Dict,           # Raw price data from broker
                'broker_margin': Dict           # Raw margin data from broker
            }

        Raises:
            PriceFetchError: If price fetch fails
            MarginFetchError: If margin fetch fails
            ValueError: If signal is invalid
        """
        ticker = signal.get('instrument')
        if not ticker:
            raise ValueError("Signal must contain 'instrument' field")

        action = signal.get('action', 'BUY').upper()
        order_type = signal.get('order_type', 'MARKET').upper()
        limit_price = signal.get('limit_price') or signal.get('price')

        # Step 1: Fetch current price from broker
        self.logger.info(f"Fetching current price for {ticker} from broker...")
        try:
            # Pass signal to broker for potential signal_price fallback
            broker_price = self.fetch_current_price(ticker, signal=signal)
            current_market_price = broker_price['price']
            self.logger.info(f"✅ Current market price for {ticker}: ${current_market_price:.4f}")
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch price for {ticker}: {e}")
            raise PriceFetchError(f"Cannot fetch price for {ticker}: {e}")

        # Step 2: Determine price to use for margin calculation
        if order_type == 'LIMIT':
            if not limit_price:
                raise ValueError("LIMIT order requires limit_price in signal")

            # Use worse-case price for margin calculation
            if action == 'BUY':
                # Buying: could fill at limit price (higher than market)
                price_for_margin = max(current_market_price, float(limit_price))
                self.logger.info(f"LIMIT BUY: Using worse-case price ${price_for_margin:.4f} "
                               f"(market: ${current_market_price:.4f}, limit: ${limit_price:.4f})")
            else:  # SELL
                # Selling: could fill at limit price (lower than market)
                price_for_margin = min(current_market_price, float(limit_price))
                self.logger.info(f"LIMIT SELL: Using worse-case price ${price_for_margin:.4f} "
                               f"(market: ${current_market_price:.4f}, limit: ${limit_price:.4f})")
        else:  # MARKET
            price_for_margin = current_market_price
            self.logger.info(f"MARKET order: Using current price ${price_for_margin:.4f}")

        # Step 3: Calculate quantity from position capital
        if price_for_margin <= 0:
            raise ValueError(f"Invalid price for {ticker}: ${price_for_margin}")

        estimated_quantity = position_capital / price_for_margin
        self.logger.info(f"Estimated quantity: {estimated_quantity:.2f} "
                        f"(${position_capital:.2f} / ${price_for_margin:.4f})")

        # Step 4: Fetch margin requirement from broker
        self.logger.info(f"Fetching margin requirement for {ticker} x {estimated_quantity:.2f}...")
        try:
            broker_margin = self.fetch_margin_requirement(
                ticker,
                estimated_quantity,
                price_for_margin
            )
            initial_margin = broker_margin['initial_margin']
            self.logger.info(f"✅ Margin requirement: ${initial_margin:.2f}")
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch margin for {ticker}: {e}")
            raise MarginFetchError(f"Cannot fetch margin for {ticker}: {e}")

        # Step 5: Validate margin is available
        if initial_margin > account_equity:
            self.logger.warning(f"⚠️ Insufficient margin: need ${initial_margin:.2f}, "
                              f"have ${account_equity:.2f}")

        # Calculate notional value
        notional_value = estimated_quantity * price_for_margin

        return {
            'quantity': estimated_quantity,
            'price_used': price_for_margin,
            'notional_value': notional_value,
            'initial_margin': initial_margin,
            'margin_pct': broker_margin.get('margin_pct', 0),
            'calculation_method': broker_margin.get('calculation_method', 'Broker-provided'),
            'broker_price': broker_price,
            'broker_margin': broker_margin,
            'validation': {
                'margin_available': account_equity >= initial_margin,
                'account_equity': account_equity,
                'margin_utilization': (initial_margin / account_equity * 100) if account_equity > 0 else 0
            }
        }
