#!/usr/bin/env python3
"""
Portfolio Models for Mathematricks Trader
Defines Current, Ideal, and Updated portfolio structures
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class Broker(Enum):
    """Supported brokers"""
    IBKR = "ibkr"
    ZERODHA = "zerodha"
    BINANCE = "binance"
    VANTAGE = "vantage"


class AssetType(Enum):
    """Asset types"""
    STOCK = "stock"
    OPTION = "option"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"


@dataclass
class Position:
    """Individual position in a portfolio"""
    ticker: str
    broker: Broker
    asset_type: AssetType
    quantity: float
    avg_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    metadata: Dict = field(default_factory=dict)  # For option strike, expiry, etc.

    def __post_init__(self):
        if self.current_price and self.market_value is None:
            self.market_value = self.quantity * self.current_price
        if self.current_price and self.unrealized_pnl is None:
            self.unrealized_pnl = (self.current_price - self.avg_price) * self.quantity


@dataclass
class CurrentPortfolio:
    """
    Current portfolio - aggregated from all brokers
    This is the real-time state of all positions
    """
    positions: Dict[str, Position] = field(default_factory=dict)  # key: ticker_broker
    total_value: float = 0.0
    cash_by_broker: Dict[Broker, float] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

    def add_position(self, position: Position):
        """Add or update a position"""
        key = f"{position.ticker}_{position.broker.value}"
        self.positions[key] = position
        self._recalculate_total_value()

    def get_position(self, ticker: str, broker: Broker) -> Optional[Position]:
        """Get a specific position"""
        key = f"{ticker}_{broker.value}"
        return self.positions.get(key)

    def get_positions_by_broker(self, broker: Broker) -> List[Position]:
        """Get all positions for a specific broker"""
        return [pos for pos in self.positions.values() if pos.broker == broker]

    def _recalculate_total_value(self):
        """Recalculate total portfolio value"""
        positions_value = sum(
            pos.market_value for pos in self.positions.values()
            if pos.market_value
        )
        cash_value = sum(self.cash_by_broker.values())
        self.total_value = positions_value + cash_value


@dataclass
class IdealPortfolio(CurrentPortfolio):
    """
    Ideal portfolio - risk-adjusted version of current portfolio
    This is what the portfolio should look like after risk management
    """
    risk_score: float = 0.0
    adjustments_made: List[str] = field(default_factory=list)
    risk_metrics: Dict = field(default_factory=dict)

    @classmethod
    def from_current(cls, current: CurrentPortfolio, risk_score: float = 0.0):
        """Create IdealPortfolio from CurrentPortfolio"""
        return cls(
            positions=current.positions.copy(),
            total_value=current.total_value,
            cash_by_broker=current.cash_by_broker.copy(),
            last_updated=current.last_updated,
            risk_score=risk_score
        )


@dataclass
class UpdatedPortfolio(CurrentPortfolio):
    """
    Updated portfolio - current portfolio + new signal
    This is what the portfolio would look like after executing a signal
    """
    new_positions: List[Position] = field(default_factory=list)
    signal_id: Optional[str] = None
    strategy_name: Optional[str] = None

    @classmethod
    def from_current_with_signal(
        cls,
        current: CurrentPortfolio,
        new_positions: List[Position],
        signal_id: str = None,
        strategy_name: str = None
    ):
        """Create UpdatedPortfolio by applying new positions to current"""
        updated = cls(
            positions=current.positions.copy(),
            total_value=current.total_value,
            cash_by_broker=current.cash_by_broker.copy(),
            last_updated=datetime.now(),
            new_positions=new_positions,
            signal_id=signal_id,
            strategy_name=strategy_name
        )

        # Add new positions
        for pos in new_positions:
            updated.add_position(pos)

        return updated


@dataclass
class PortfolioSummary:
    """Summary statistics for a portfolio"""
    total_value: float
    total_positions: int
    positions_by_broker: Dict[str, int]
    positions_by_asset_type: Dict[str, int]
    total_unrealized_pnl: float
    largest_position: Optional[Position] = None

    @classmethod
    def from_portfolio(cls, portfolio: CurrentPortfolio):
        """Generate summary from portfolio"""
        positions_by_broker = {}
        positions_by_asset_type = {}
        total_unrealized_pnl = 0.0
        largest_position = None
        max_value = 0.0

        for pos in portfolio.positions.values():
            # By broker
            broker_name = pos.broker.value
            positions_by_broker[broker_name] = positions_by_broker.get(broker_name, 0) + 1

            # By asset type
            asset_name = pos.asset_type.value
            positions_by_asset_type[asset_name] = positions_by_asset_type.get(asset_name, 0) + 1

            # PnL
            if pos.unrealized_pnl:
                total_unrealized_pnl += pos.unrealized_pnl

            # Largest position
            if pos.market_value and pos.market_value > max_value:
                max_value = pos.market_value
                largest_position = pos

        return cls(
            total_value=portfolio.total_value,
            total_positions=len(portfolio.positions),
            positions_by_broker=positions_by_broker,
            positions_by_asset_type=positions_by_asset_type,
            total_unrealized_pnl=total_unrealized_pnl,
            largest_position=largest_position
        )
