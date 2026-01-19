"""
Precision Service - Manages quantity precision for different brokers and assets

This service queries brokers for asset precision and caches results for performance.
The broker is the authoritative source for what precision is allowed.

Cache is now stored in MongoDB for distributed system compatibility.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from pymongo import MongoClient

logger = logging.getLogger(__name__)


class PrecisionService:
    """
    Service to manage quantity precision for trading.

    Queries brokers for asset-specific precision and caches results in MongoDB.
    Cache structure: {source, symbol, precision, last_checked}
    """

    CACHE_TTL_HOURS = 24

    def __init__(self, mongo_uri: str = None):
        """
        Initialize the precision service.

        Args:
            mongo_uri: MongoDB connection URI (defaults to env variable or localhost)
        """
        if mongo_uri is None:
            mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongodb:27017/')
        
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client['mathematricks_trading']
        self.cache_collection = self.db['precision_cache']
        
        logger.info(f"PrecisionService initialized with MongoDB cache")
        
        # Ensure indexes exist
        try:
            self.cache_collection.create_index([('source', 1), ('symbol', 1)], unique=True)
        except Exception as e:
            logger.debug(f"Index already exists or creation failed: {e}")

    def _is_cache_valid(self, last_checked: datetime) -> bool:
        """
        Check if cached precision is still valid (within TTL).

        Args:
            last_checked: Datetime of last check

        Returns:
            True if cache is valid, False if expired
        """
        try:
            now = datetime.now(timezone.utc)
            # Ensure last_checked is timezone-aware
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
            age_hours = (now - last_checked).total_seconds() / 3600
            return age_hours < self.CACHE_TTL_HOURS
        except Exception as e:
            logger.warning(f"Failed to validate cache timestamp: {e}")
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
        try:
            doc = self.cache_collection.find_one({'source': broker_id, 'symbol': symbol})
            
            if doc is None:
                return None
            
            if self._is_cache_valid(doc['last_checked']):
                logger.debug(f"Using cached precision for {broker_id}/{symbol}: {doc['precision']}")
                return doc['precision']
            
            logger.debug(f"Cache expired for {broker_id}/{symbol}")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cached precision: {e}")
            return None

    def _cache_precision(self, broker_id: str, symbol: str, precision: int):
        """
        Cache precision value for an asset in MongoDB.

        Args:
            broker_id: Broker identifier
            symbol: Asset symbol
            precision: Number of decimal places
        """
        try:
            doc = {
                'source': broker_id,
                'symbol': symbol,
                'precision': precision,
                'last_checked': datetime.now(timezone.utc)
            }
            
            self.cache_collection.update_one(
                {'source': broker_id, 'symbol': symbol},
                {'$set': doc},
                upsert=True
            )
            
            logger.debug(f"Cached precision for {broker_id}/{symbol}: {precision}")
            
        except Exception as e:
            logger.error(f"Failed to cache precision: {e}")

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
        Clear precision cache in MongoDB.

        Args:
            broker_id: If provided, clear only this broker's cache
            symbol: If provided with broker_id, clear only this symbol
        """
        try:
            if broker_id and symbol:
                result = self.cache_collection.delete_one({'source': broker_id, 'symbol': symbol})
                logger.info(f"Cleared cache for {broker_id}/{symbol} ({result.deleted_count} docs)")
            elif broker_id:
                result = self.cache_collection.delete_many({'source': broker_id})
                logger.info(f"Cleared cache for {broker_id} ({result.deleted_count} docs)")
            else:
                result = self.cache_collection.delete_many({})
                logger.info(f"Cleared all precision cache ({result.deleted_count} docs)")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")


# Module-level singleton for convenience
_precision_service: Optional[PrecisionService] = None


def get_precision_service(mongo_uri: str = None) -> PrecisionService:
    """
    Get or create the precision service singleton.

    Args:
        mongo_uri: MongoDB connection URI

    Returns:
        PrecisionService instance
    """
    global _precision_service
    if _precision_service is None:
        _precision_service = PrecisionService(mongo_uri)
    return _precision_service
