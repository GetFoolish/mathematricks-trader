#!/usr/bin/env python3
"""
Risk Calculator for Mathematricks Trader
V1: Placeholder implementation with basic position sizing
Future: Advanced risk metrics, correlation analysis, VaR, etc.
"""

from typing import Dict, List
from ..core.portfolio import CurrentPortfolio, IdealPortfolio, Position


class RiskCalculator:
    """
    Calculate risk-adjusted portfolio
    V1: Simple placeholder logic
    """

    def __init__(self, config: Dict = None):
        """
        Initialize risk calculator with configuration

        Args:
            config: Risk configuration parameters
        """
        self.config = config or {}
        # V1 placeholder limits
        self.max_position_size_pct = self.config.get('max_position_size_pct', 10.0)  # 10% per position
        self.max_broker_allocation_pct = self.config.get('max_broker_allocation_pct', 40.0)  # 40% per broker

    def adjust_portfolio(self, current: CurrentPortfolio) -> IdealPortfolio:
        """
        Calculate ideal portfolio from current portfolio

        V1: Basic position sizing checks
        Future: Advanced risk modeling, correlation, VaR, etc.

        Args:
            current: Current portfolio state

        Returns:
            IdealPortfolio with risk adjustments applied
        """
        ideal = IdealPortfolio.from_current(current)
        adjustments = []

        # V1: Check position sizes
        for key, position in list(ideal.positions.items()):
            if position.market_value and ideal.total_value > 0:
                position_pct = (position.market_value / ideal.total_value) * 100

                # If position exceeds limit, flag for adjustment
                if position_pct > self.max_position_size_pct:
                    adjustments.append(
                        f"Position {position.ticker} on {position.broker.value} "
                        f"exceeds {self.max_position_size_pct}% limit "
                        f"({position_pct:.1f}%)"
                    )

        # V1: Check broker allocation
        broker_allocations = self._calculate_broker_allocations(ideal)
        for broker, allocation_pct in broker_allocations.items():
            if allocation_pct > self.max_broker_allocation_pct:
                adjustments.append(
                    f"Broker {broker} allocation exceeds "
                    f"{self.max_broker_allocation_pct}% limit "
                    f"({allocation_pct:.1f}%)"
                )

        # Calculate basic risk score (0-100, higher is riskier)
        risk_score = self._calculate_risk_score(ideal)

        ideal.adjustments_made = adjustments
        ideal.risk_score = risk_score
        ideal.risk_metrics = {
            'max_position_size_pct': self.max_position_size_pct,
            'max_broker_allocation_pct': self.max_broker_allocation_pct,
            'broker_allocations': broker_allocations,
            'total_positions': len(ideal.positions)
        }

        return ideal

    def _calculate_broker_allocations(self, portfolio: CurrentPortfolio) -> Dict[str, float]:
        """Calculate percentage allocation by broker"""
        allocations = {}

        if portfolio.total_value == 0:
            return allocations

        for broker in set(pos.broker for pos in portfolio.positions.values()):
            broker_positions = portfolio.get_positions_by_broker(broker)
            broker_value = sum(
                pos.market_value for pos in broker_positions
                if pos.market_value
            )
            allocations[broker.value] = (broker_value / portfolio.total_value) * 100

        return allocations

    def _calculate_risk_score(self, portfolio: IdealPortfolio) -> float:
        """
        Calculate risk score for portfolio (0-100)
        V1: Simple concentration-based score
        Future: VaR, Sharpe ratio, correlation, etc.
        """
        if not portfolio.positions:
            return 0.0

        # Concentration risk
        position_count = len(portfolio.positions)
        concentration_penalty = max(0, 50 - (position_count * 5))  # More positions = lower risk

        # Position size risk
        max_position_pct = 0.0
        if portfolio.total_value > 0:
            for pos in portfolio.positions.values():
                if pos.market_value:
                    pct = (pos.market_value / portfolio.total_value) * 100
                    max_position_pct = max(max_position_pct, pct)

        size_penalty = min(max_position_pct * 2, 40)  # Cap at 40 points

        # Broker concentration risk
        broker_allocations = self._calculate_broker_allocations(portfolio)
        max_broker_allocation = max(broker_allocations.values()) if broker_allocations else 0
        broker_penalty = min(max_broker_allocation / 2, 20)  # Cap at 20 points

        risk_score = min(concentration_penalty + size_penalty + broker_penalty, 100)
        return round(risk_score, 2)
