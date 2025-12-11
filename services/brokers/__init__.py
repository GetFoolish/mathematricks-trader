"""
Shared Broker Library for Mathematricks Trading System

This library provides a unified interface for interacting with multiple brokers.
All broker implementations follow the AbstractBroker interface.

Available Brokers:
- IBKR (Interactive Brokers) - US stocks, options, futures, forex
- Zerodha (Kite Connect) - Indian stocks, derivatives, commodities

Usage:
    from brokers import BrokerFactory

    # Create IBKR broker
    config = {
        "broker": "IBKR",
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 1,
        "account_id": "DU123456"
    }
    broker = BrokerFactory.create_broker(config)
    broker.connect()

    # Place order
    result = broker.place_order({
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 100,
        "order_type": "MARKET"
    })

    # Get account balance
    balance = broker.get_account_balance()

For more information, see README.md
"""

# Export factory and base classes
from .factory import BrokerFactory, create_broker_from_env
from .base import AbstractBroker, OrderSide, OrderType, OrderStatus

# Export exceptions
from .exceptions import (
    BrokerError,
    BrokerConnectionError,
    OrderRejectedError,
    OrderNotFoundError,
    BrokerAPIError,
    InsufficientFundsError,
    InvalidSymbolError,
    MarketClosedError,
    AuthenticationError,
    BrokerTimeoutError
)

# Export broker implementations
from .ibkr import IBKRBroker
from .zerodha import ZerodhaBroker
from .mock import MockBroker

__all__ = [
    # Factory
    'BrokerFactory',
    'create_broker_from_env',

    # Base classes
    'AbstractBroker',
    'OrderSide',
    'OrderType',
    'OrderStatus',

    # Exceptions
    'BrokerError',
    'BrokerConnectionError',
    'OrderRejectedError',
    'OrderNotFoundError',
    'BrokerAPIError',
    'InsufficientFundsError',
    'InvalidSymbolError',
    'MarketClosedError',
    'AuthenticationError',
    'BrokerTimeoutError',

    # Broker implementations
    'IBKRBroker',
    'ZerodhaBroker',
    'MockBroker',
]

__version__ = '1.0.0'
