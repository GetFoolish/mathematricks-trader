"""
Broker Factory
Creates broker instances based on configuration
"""
import logging
from typing import Dict, Any

from .base import AbstractBroker
from .ibkr import IBKRBroker
from .zerodha import ZerodhaBroker
from .mock import MockBroker
from .exceptions import BrokerError

logger = logging.getLogger(__name__)


class BrokerFactory:
    """
    Factory for creating broker instances.

    Usage:
        config = {
            "broker": "IBKR",
            "host": "127.0.0.1",
            "port": 7497,
            "client_id": 1,
            "account_id": "DU123456"
        }
        broker = BrokerFactory.create_broker(config)
        broker.connect()
    """

    # Registry of available brokers
    BROKERS = {
        "IBKR": IBKRBroker,
        "Zerodha": ZerodhaBroker,
        "Mock": MockBroker,
        # Add more brokers here as they're implemented
    }

    @staticmethod
    def create_broker(config: Dict[str, Any]) -> AbstractBroker:
        """
        Create a broker instance based on configuration.

        Args:
            config: Broker configuration dict with "broker" field specifying broker name

        Returns:
            Broker instance implementing AbstractBroker interface

        Raises:
            BrokerError: If broker name is invalid or not supported
            ValueError: If config is missing required fields

        Example configs:

        IBKR:
        {
            "broker": "IBKR",
            "host": "127.0.0.1",
            "port": 7497,
            "client_id": 1,
            "account_id": "DU123456"
        }

        Zerodha:
        {
            "broker": "Zerodha",
            "api_key": "your_api_key",
            "api_secret": "your_api_secret",
            "access_token": "your_access_token",
            "user_id": "AB1234"
        }
        """
        if not config:
            raise ValueError("Broker config cannot be empty")

        broker_name = config.get("broker")
        if not broker_name:
            raise ValueError("Missing 'broker' field in config")

        # Normalize broker name (case-insensitive)
        broker_name = broker_name.strip()
        for registered_name in BrokerFactory.BROKERS.keys():
            if broker_name.upper() == registered_name.upper():
                broker_name = registered_name
                break

        if broker_name not in BrokerFactory.BROKERS:
            available = ", ".join(BrokerFactory.BROKERS.keys())
            raise BrokerError(
                f"Unsupported broker: '{broker_name}'. Available brokers: {available}",
                broker_name=broker_name
            )

        broker_class = BrokerFactory.BROKERS[broker_name]

        try:
            logger.info(f"Creating {broker_name} broker instance...")
            broker = broker_class(config)
            logger.info(f"✅ {broker_name} broker instance created")
            return broker

        except Exception as e:
            logger.error(f"Failed to create {broker_name} broker: {e}", exc_info=True)
            raise BrokerError(
                f"Failed to create {broker_name} broker: {str(e)}",
                broker_name=broker_name,
                details={"error": str(e)}
            )

    @staticmethod
    def get_supported_brokers() -> list:
        """
        Get list of supported broker names.

        Returns:
            List of broker names (e.g., ["IBKR", "Zerodha"])
        """
        return list(BrokerFactory.BROKERS.keys())

    @staticmethod
    def register_broker(name: str, broker_class: type):
        """
        Register a new broker implementation.

        This allows adding custom brokers at runtime.

        Args:
            name: Broker name (e.g., "Alpaca")
            broker_class: Broker class implementing AbstractBroker

        Raises:
            ValueError: If broker_class doesn't implement AbstractBroker

        Example:
            from brokers.base import AbstractBroker

            class AlpacaBroker(AbstractBroker):
                ...

            BrokerFactory.register_broker("Alpaca", AlpacaBroker)
        """
        if not issubclass(broker_class, AbstractBroker):
            raise ValueError(f"Broker class must implement AbstractBroker interface")

        BrokerFactory.BROKERS[name] = broker_class
        logger.info(f"Registered broker: {name}")


def create_broker_from_env(broker_name: str = None) -> AbstractBroker:
    """
    Convenience function to create broker from environment variables.

    Reads broker configuration from environment variables:
    - BROKER_NAME (if broker_name not provided)
    - IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID, IBKR_ACCOUNT_ID (for IBKR)
    - ZERODHA_API_KEY, ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN, ZERODHA_USER_ID (for Zerodha)

    Args:
        broker_name: Broker name (reads from BROKER_NAME env var if not provided)

    Returns:
        Broker instance

    Example:
        # Set environment variables first
        export BROKER_NAME=IBKR
        export IBKR_HOST=127.0.0.1
        export IBKR_PORT=7497
        export IBKR_CLIENT_ID=1
        export IBKR_ACCOUNT_ID=DU123456

        # Then create broker
        broker = create_broker_from_env()
    """
    import os

    if not broker_name:
        broker_name = os.getenv("BROKER_NAME")
        if not broker_name:
            raise ValueError("broker_name not provided and BROKER_NAME env var not set")

    broker_name = broker_name.upper()

    if broker_name == "IBKR":
        config = {
            "broker": "IBKR",
            "host": os.getenv("IBKR_HOST", "127.0.0.1"),
            "port": int(os.getenv("IBKR_PORT", "7497")),
            "client_id": int(os.getenv("IBKR_CLIENT_ID", "1")),
            "account_id": os.getenv("IBKR_ACCOUNT_ID")
        }
    elif broker_name == "ZERODHA":
        config = {
            "broker": "Zerodha",
            "api_key": os.getenv("ZERODHA_API_KEY"),
            "api_secret": os.getenv("ZERODHA_API_SECRET"),
            "access_token": os.getenv("ZERODHA_ACCESS_TOKEN"),
            "user_id": os.getenv("ZERODHA_USER_ID")
        }
    else:
        raise ValueError(f"Unsupported broker: {broker_name}")

    return BrokerFactory.create_broker(config)
