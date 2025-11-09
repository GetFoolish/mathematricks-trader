"""
Data structures for portfolio construction context and decisions.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd


@dataclass
class Position:
    """Represents an open position"""
    instrument: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    margin_required: float
    strategy_id: Optional[str] = None


@dataclass
class Order:
    """Represents an open order"""
    order_id: str
    instrument: str
    side: str  # "BUY" or "SELL"
    quantity: float
    order_type: str  # "MARKET", "LIMIT", etc.
    price: float
    strategy_id: Optional[str] = None


@dataclass
class Signal:
    """Standardized trading signal"""
    signal_id: str
    strategy_id: str
    timestamp: datetime
    instrument: str
    direction: str  # "LONG" or "SHORT"
    action: str  # "ENTRY" or "EXIT"
    order_type: str  # "MARKET", "LIMIT", "STOP"
    price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    expiry: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalDecision:
    """Decision made by portfolio constructor for a signal"""
    action: str  # "APPROVE", "REJECT", "RESIZE"
    quantity: float
    reason: str
    allocated_capital: Optional[float] = None
    margin_required: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioContext:
    """
    Unified context for both research and production.
    Contains all data needed to make portfolio decisions.
    """
    # Account State
    account_equity: float
    margin_used: float
    margin_available: float
    cash_balance: float
    
    # Current Portfolio
    open_positions: List[Position]
    open_orders: List[Order]
    current_allocations: Dict[str, float]  # {strategy_id: allocation_pct}
    
    # Historical Data (for research/backtesting)
    strategy_histories: Dict[str, pd.DataFrame] = field(default_factory=dict)
    correlation_matrix: Optional[pd.DataFrame] = None
    
    # Risk Metrics
    total_exposure: float = 0.0
    strategy_exposures: Dict[str, float] = field(default_factory=dict)
    
    # Mode flag
    is_backtest: bool = False
    current_date: Optional[datetime] = None
    
    def get_margin_utilization_pct(self) -> float:
        """Calculate current margin utilization percentage"""
        if self.account_equity <= 0:
            return 100.0
        return (self.margin_used / self.account_equity) * 100
    
    def get_strategy_correlation(self, strategy1: str, strategy2: str) -> float:
        """Get correlation between two strategies"""
        if self.correlation_matrix is None:
            return 0.0
        
        try:
            return self.correlation_matrix.loc[strategy1, strategy2]
        except (KeyError, AttributeError):
            return 0.0
    
    def get_total_risk(self) -> float:
        """Calculate total portfolio risk (simplified as margin used)"""
        return self.margin_used
    
    def get_strategy_exposure(self, strategy_id: str) -> float:
        """Get current exposure for a specific strategy"""
        return self.strategy_exposures.get(strategy_id, 0.0)
