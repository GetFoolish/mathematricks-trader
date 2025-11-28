"""
Base class for all portfolio construction strategies.
All constructors must inherit from this class.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from .context import PortfolioContext, Signal, SignalDecision


class PortfolioConstructor(ABC):
    """
    Base class for all portfolio construction strategies.
    Handles both research (backtesting) and production (live signals).
    
    The same code runs in both modes - just with different context data!
    """
    
    def __init__(self, **kwargs):
        """
        Initialize constructor with configuration parameters.
        Override this to accept strategy-specific parameters.
        """
        self.config = kwargs
    
    @abstractmethod
    def allocate_portfolio(self, context: PortfolioContext) -> Dict[str, float]:
        """
        Decide how to allocate capital across strategies.
        
        This is called:
        - In research: For each rebalance period in walk-forward analysis
        - In production: Periodically (daily/weekly) or on-demand
        
        Args:
            context: Contains historical data, current positions, account state
            
        Returns:
            Dict of {strategy_id: allocation_pct}
            Example: {"SPX_1D": 45.5, "Forex": 30.2, "Gold": 24.3}
            
        Note: Allocations can sum to >100% for leveraged portfolios
        """
        pass
    
    @abstractmethod
    def evaluate_signal(self, signal: Signal, context: PortfolioContext) -> SignalDecision:
        """
        Decide what to do with an incoming signal.
        
        This is called:
        - In research: For each signal in backtest
        - In production: For each live signal
        
        Args:
            signal: The incoming trade signal
            context: Current portfolio state, allocations, account metrics
            
        Returns:
            SignalDecision with:
            - action: "APPROVE", "REJECT", or "RESIZE"
            - quantity: Final position size
            - reason: Explanation for the decision
            - allocated_capital: Capital allocated to this trade
            - margin_required: Estimated margin needed
        """
        pass
    
    def calculate_metrics(self, context: PortfolioContext) -> Dict[str, Any]:
        """
        Calculate custom metrics for this strategy.
        Override to add your own metrics beyond standard ones.
        
        Returns:
            Dict of metric_name: metric_value
            Example: {"portfolio_sharpe": 1.8, "max_correlation": 0.65}
        """
        return {}
    
    def on_rebalance(self, context: PortfolioContext) -> None:
        """
        Hook called when portfolio is rebalanced.
        Override to perform custom actions on rebalance.
        """
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return self.config.copy()
