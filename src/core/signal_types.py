#!/usr/bin/env python3
"""
Signal Types for Mathematricks Trader
Defines all signal types based on https://mathematricks.fund/api/signals_documentation
"""

from enum import Enum
from typing import Dict, List, Union, Any
from dataclasses import dataclass
from datetime import datetime


class SignalType(Enum):
    """Enumeration of all supported signal types"""
    STOCK = "stock"
    OPTIONS = "options"
    MULTI_LEG = "multi_leg"
    STOP_LOSS = "stop_loss"


class Action(Enum):
    """Trading actions"""
    BUY = "BUY"
    SELL = "SELL"
    BUY_CALL = "BUY_CALL"
    BUY_PUT = "BUY_PUT"
    SELL_CALL = "SELL_CALL"
    SELL_PUT = "SELL_PUT"
    SELL_ALL = "SELL_ALL"


@dataclass
class StockSignal:
    """Stock trading signal"""
    ticker: str
    action: str
    price: float

    @classmethod
    def from_dict(cls, data: Dict) -> 'StockSignal':
        return cls(
            ticker=data['ticker'],
            action=data['action'],
            price=data['price']
        )


@dataclass
class OptionsSignal:
    """Options trading signal"""
    type: str
    ticker: str
    strike: float
    expiry: str
    action: str

    @classmethod
    def from_dict(cls, data: Dict) -> 'OptionsSignal':
        return cls(
            type=data['type'],
            ticker=data['ticker'],
            strike=data['strike'],
            expiry=data['expiry'],
            action=data['action']
        )


@dataclass
class LegOrder:
    """Single leg of a multi-leg order"""
    ticker: str
    action: str
    qty: int


@dataclass
class MultiLegSignal:
    """Multi-leg trading signal"""
    legs: List[LegOrder]

    @classmethod
    def from_dict(cls, data: List[Dict]) -> 'MultiLegSignal':
        legs = [LegOrder(**leg) for leg in data]
        return cls(legs=legs)


@dataclass
class StopLossSignal:
    """Stop-loss trading signal"""
    trigger: str
    action: str
    stop_loss: bool

    @classmethod
    def from_dict(cls, data: Dict) -> 'StopLossSignal':
        return cls(
            trigger=data['trigger'],
            action=data['action'],
            stop_loss=data['stop_loss']
        )


@dataclass
class TradingSignal:
    """
    Wrapper for all trading signals with metadata
    Contains the required fields from the webhook plus the signal data
    """
    strategy_name: str
    signal_sent_EPOCH: int
    signalID: str
    timestamp: str
    signal: Union[StockSignal, OptionsSignal, MultiLegSignal, StopLossSignal]
    signal_type: SignalType

    @classmethod
    def from_webhook(cls, data: Dict) -> 'TradingSignal':
        """Create TradingSignal from webhook data"""
        signal_data = data['signal']

        # Determine signal type
        if isinstance(signal_data, list):
            signal_type = SignalType.MULTI_LEG
            signal = MultiLegSignal.from_dict(signal_data)
        elif 'type' in signal_data and signal_data['type'] == 'options':
            signal_type = SignalType.OPTIONS
            signal = OptionsSignal.from_dict(signal_data)
        elif 'stop_loss' in signal_data and signal_data['stop_loss']:
            signal_type = SignalType.STOP_LOSS
            signal = StopLossSignal.from_dict(signal_data)
        else:
            signal_type = SignalType.STOCK
            signal = StockSignal.from_dict(signal_data)

        return cls(
            strategy_name=data['strategy_name'],
            signal_sent_EPOCH=data['signal_sent_EPOCH'],
            signalID=data['signalID'],
            timestamp=data['timestamp'],
            signal=signal,
            signal_type=signal_type
        )
