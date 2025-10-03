#!/usr/bin/env python3
"""
Base Broker Interface for Mathematricks Trader
All broker implementations must inherit from this class
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from ..core.portfolio import Position, Broker
from ..order_management.order_types import MathematricksOrder, OrderConfirmation


class BaseBroker(ABC):
    """
    Abstract base class for all broker integrations
    """

    def __init__(self, broker_type: Broker, config: Dict = None):
        """
        Initialize broker

        Args:
            broker_type: Broker enum type
            config: Broker configuration (API keys, etc.)
        """
        self.broker_type = broker_type
        self.config = config or {}
        self.is_connected = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to broker API

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from broker API"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Fetch current positions from broker

        Returns:
            List of Position objects
        """
        pass

    @abstractmethod
    def get_account_balance(self) -> Dict[str, float]:
        """
        Get account cash balance

        Returns:
            Dictionary with currency and balance
        """
        pass

    @abstractmethod
    def convert_order(self, order: MathematricksOrder) -> Dict:
        """
        Convert Mathematricks order to broker-specific order format

        Args:
            order: Mathematricks order

        Returns:
            Broker-specific order dictionary
        """
        pass

    @abstractmethod
    def send_order(self, order: MathematricksOrder) -> OrderConfirmation:
        """
        Send order to broker

        Args:
            order: Mathematricks order to execute

        Returns:
            OrderConfirmation with execution details
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderConfirmation:
        """
        Get status of an order

        Args:
            order_id: Broker order ID

        Returns:
            OrderConfirmation with current status
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order

        Args:
            order_id: Broker order ID

        Returns:
            True if cancelled successfully, False otherwise
        """
        pass

    def validate_order(self, order: MathematricksOrder) -> tuple[bool, Optional[str]]:
        """
        Validate order before sending to broker
        Can be overridden by specific broker implementations

        Args:
            order: Order to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation
        if order.quantity <= 0:
            return False, "Quantity must be positive"

        if order.ticker is None or order.ticker == "":
            return False, "Ticker is required"

        return True, None

    def __str__(self):
        return f"{self.broker_type.value.upper()} Broker ({'Connected' if self.is_connected else 'Disconnected'})"
