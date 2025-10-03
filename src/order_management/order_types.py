#!/usr/bin/env python3
"""
Order Types for Mathematricks Trader
Standardized order format that all brokers understand
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime
from enum import Enum
from ..core.portfolio import Broker, AssetType


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TimeInForce(Enum):
    """Time in force"""
    DAY = "day"
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


@dataclass
class MathematricksOrder:
    """
    Standardized order format for Mathematricks Trader
    All signals are converted to this format before broker execution
    """
    # Core fields
    ticker: str
    broker: Broker
    asset_type: AssetType
    order_side: OrderSide
    quantity: float
    order_type: OrderType

    # Optional fields
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY

    # Metadata
    signal_id: Optional[str] = None
    strategy_name: Optional[str] = None
    order_id: Optional[str] = None  # Assigned by broker
    created_at: datetime = field(default_factory=datetime.now)
    status: OrderStatus = OrderStatus.PENDING

    # Options-specific fields
    option_type: Optional[str] = None  # 'call' or 'put'
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None

    # Stop-loss specific
    is_stop_loss: bool = False
    trigger_condition: Optional[str] = None

    # Multi-leg specific
    leg_number: Optional[int] = None  # For multi-leg orders
    parent_order_id: Optional[str] = None

    # Execution details (filled by broker)
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    commission: float = 0.0

    # Additional metadata
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert order to dictionary for storage"""
        return {
            'ticker': self.ticker,
            'broker': self.broker.value,
            'asset_type': self.asset_type.value,
            'order_side': self.order_side.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'time_in_force': self.time_in_force.value,
            'signal_id': self.signal_id,
            'strategy_name': self.strategy_name,
            'order_id': self.order_id,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value,
            'option_type': self.option_type,
            'strike_price': self.strike_price,
            'expiry_date': self.expiry_date,
            'is_stop_loss': self.is_stop_loss,
            'trigger_condition': self.trigger_condition,
            'leg_number': self.leg_number,
            'parent_order_id': self.parent_order_id,
            'filled_quantity': self.filled_quantity,
            'avg_fill_price': self.avg_fill_price,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'commission': self.commission,
            'metadata': self.metadata
        }


@dataclass
class OrderConfirmation:
    """
    Order confirmation from broker
    """
    order_id: str
    broker_order_id: str
    status: OrderStatus
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    commission: float = 0.0
    filled_at: Optional[datetime] = None
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert confirmation to dictionary"""
        return {
            'order_id': self.order_id,
            'broker_order_id': self.broker_order_id,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'avg_fill_price': self.avg_fill_price,
            'commission': self.commission,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'message': self.message,
            'error': self.error
        }
