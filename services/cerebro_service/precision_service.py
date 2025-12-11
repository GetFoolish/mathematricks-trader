"""
Precision Service - Manages quantity precision for different brokers and assets

This service queries brokers for asset precision and caches results for performance.
The broker is the authoritative source for what precision is allowed.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PrecisionService:
    """
    Service to manage quantity precision for trading.

    Queries brokers for asset-specific precision and caches results.
    Cache is structured as: broker_id -> symbol -> {precision, last_checked}
    """

    CACHE_FILE = "data/precision_cache.json"
    CACHE_TTL_HOURS = 24

    def __init__(self, project_root: str = None):
        """
        Initialize the precision service.

        Args:
            project_root: Root directory of the project (for cache file path)
        """
        if project_root:
            self.cache_file = os.path.join(project_root, self.CACHE_FILE)
        else:
            # Try to find project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            self.cache_file = os.path.join(project_root, self.CACHE_FILE)

        self.cache = self._load_cache()
        logger.info(f"PrecisionService initialized with cache at {self.cache_file}")

    def _load_cache(self) -> Dict[str, Any]:
        """Load precision cache from file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    logger.debug(f"Loaded precision cache with {len(cache)} brokers")
                    return cache
        except Exception as e:
            logger.warning(f"Failed to load precision cache: {e}")

        return {}

    def _save_cache(self):
        """Save precision cache to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.debug(f"Saved precision cache")
        except Exception as e:
            logger.error(f"Failed to save precision cache: {e}")

    def _is_cache_valid(self, last_checked: str) -> bool:
        """
        Check if cached precision is still valid (within TTL).

        Args:
            last_checked: ISO format timestamp

        Returns:
            True if cache is valid, False if expired
        """
        try:
            checked_time = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age_hours = (now - checked_time).total_seconds() / 3600
            return age_hours < self.CACHE_TTL_HOURS
        except Exception as e:
            logger.warning(f"Failed to parse cache timestamp: {e}")
            return False

    def _get_cached_precision(self, broker_id: str, symbol: str) -> Optional[int]:
        """
        Get cached precision if valid.

        Args:
            broker_id: Broker identifier (e.g., "Mock_Paper", "IBKR_Paper")
            symbol: Asset symbol (e.g., "AAPL", "EURUSD")

        Returns:
            Precision value if cached and valid, None otherwise
        """
        if broker_id not in self.cache:
            return None

        if symbol not in self.cache[broker_id]:
            return None

        entry = self.cache[broker_id][symbol]
        if self._is_cache_valid(entry.get('last_checked', '')):
            logger.debug(f"Using cached precision for {broker_id}/{symbol}: {entry['precision']}")
            return entry['precision']

        logger.debug(f"Cache expired for {broker_id}/{symbol}")
        return None

    def _cache_precision(self, broker_id: str, symbol: str, precision: int):
        """
        Cache precision value for an asset.

        Args:
            broker_id: Broker identifier
            symbol: Asset symbol
            precision: Number of decimal places
        """
        if broker_id not in self.cache:
            self.cache[broker_id] = {}

        self.cache[broker_id][symbol] = {
            'precision': precision,
            'last_checked': datetime.now(timezone.utc).isoformat()
        }

        self._save_cache()
        logger.debug(f"Cached precision for {broker_id}/{symbol}: {precision}")

    def get_precision(
        self,
        broker,  # AbstractBroker instance
        broker_id: str,
        symbol: str,
        instrument_type: str
    ) -> int:
        """
        Get quantity precision for an asset from broker.

        Uses cache if valid, otherwise queries broker and caches result.

        Args:
            broker: Broker instance with get_quantity_precision method
            broker_id: Broker identifier (e.g., "Mock_Paper", "IBKR_Paper")
            symbol: Asset symbol (e.g., "AAPL", "EURUSD")
            instrument_type: Type of instrument (e.g., "STOCK", "FOREX")

        Returns:
            Number of decimal places allowed for quantity
        """
        # Check cache first
        cached = self._get_cached_precision(broker_id, symbol)
        if cached is not None:
            return cached

        # Query broker
        try:
            precision = broker.get_quantity_precision(symbol, instrument_type)
            logger.info(f"Queried broker for precision: {broker_id}/{symbol} = {precision} decimals")
        except Exception as e:
            logger.warning(f"Failed to query broker for precision: {e}")
            # Fallback to safe defaults
            precision = self._get_default_precision(instrument_type)
            logger.info(f"Using default precision for {instrument_type}: {precision} decimals")

        # Cache result
        self._cache_precision(broker_id, symbol, precision)

        return precision

    def _get_default_precision(self, instrument_type: str) -> int:
        """
        Get default precision when broker query fails.

        Args:
            instrument_type: Type of instrument

        Returns:
            Default number of decimal places
        """
        defaults = {
            'STOCK': 0,
            'OPTION': 0,
            'FUTURE': 0,
            'FOREX': 0,
            'CRYPTO': 8,
        }
        return defaults.get(instrument_type.upper(), 0)

    def normalize_quantity(self, quantity: float, precision: int) -> float:
        """
        Normalize quantity to the specified precision.

        Args:
            quantity: Raw calculated quantity
            precision: Number of decimal places

        Returns:
            Normalized quantity
        """
        if precision == 0:
            return float(round(quantity))
        return round(quantity, precision)

    def clear_cache(self, broker_id: str = None, symbol: str = None):
        """
        Clear precision cache.

        Args:
            broker_id: If provided, clear only this broker's cache
            symbol: If provided with broker_id, clear only this symbol
        """
        if broker_id and symbol:
            if broker_id in self.cache and symbol in self.cache[broker_id]:
                del self.cache[broker_id][symbol]
                logger.info(f"Cleared cache for {broker_id}/{symbol}")
        elif broker_id:
            if broker_id in self.cache:
                del self.cache[broker_id]
                logger.info(f"Cleared cache for {broker_id}")
        else:
            self.cache = {}
            logger.info("Cleared all precision cache")

        self._save_cache()


# Module-level singleton for convenience
_precision_service: Optional[PrecisionService] = None


def get_precision_service(project_root: str = None) -> PrecisionService:
    """
    Get or create the precision service singleton.

    Args:
        project_root: Root directory of the project

    Returns:
        PrecisionService instance
    """
    global _precision_service
    if _precision_service is None:
        _precision_service = PrecisionService(project_root)
    return _precision_service
