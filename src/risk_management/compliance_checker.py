#!/usr/bin/env python3
"""
Compliance Checker for Mathematricks Trader
V1: Basic compliance checks
Future: Advanced compliance rules, regulatory requirements
"""

from typing import Tuple, List, Dict
from ..core.portfolio import UpdatedPortfolio
from ..core.signal_types import TradingSignal, SignalType, Action


class ComplianceChecker:
    """
    Check if portfolio complies with risk rules
    V1: Basic position size and allocation checks
    """

    def __init__(self, config: Dict = None):
        """
        Initialize compliance checker

        Args:
            config: Compliance configuration
        """
        self.config = config or {}
        self.max_position_size_pct = self.config.get('max_position_size_pct', 10.0)
        self.max_broker_allocation_pct = self.config.get('max_broker_allocation_pct', 40.0)
        self.max_portfolio_leverage = self.config.get('max_portfolio_leverage', 1.0)

    def check_compliance(
        self,
        updated_portfolio: UpdatedPortfolio
    ) -> Tuple[bool, List[TradingSignal]]:
        """
        Check if updated portfolio is compliant

        V1: Simple position size and broker allocation checks
        Future: Complex compliance rules, margin requirements, etc.

        Args:
            updated_portfolio: Portfolio after applying new signal

        Returns:
            Tuple of (is_compliant, rebalance_signals)
            - is_compliant: True if portfolio passes all checks
            - rebalance_signals: List of signals to rebalance if not compliant
        """
        violations = []
        rebalance_signals = []

        # Check position sizes
        position_violations = self._check_position_sizes(updated_portfolio)
        violations.extend(position_violations)

        # Check broker allocations
        broker_violations = self._check_broker_allocations(updated_portfolio)
        violations.extend(broker_violations)

        # Check leverage (V1: simple check)
        leverage_violations = self._check_leverage(updated_portfolio)
        violations.extend(leverage_violations)

        is_compliant = len(violations) == 0

        # If not compliant, generate rebalance signals (V1: placeholder)
        if not is_compliant:
            rebalance_signals = self._generate_rebalance_signals(
                updated_portfolio,
                violations
            )

        return is_compliant, rebalance_signals

    def _check_position_sizes(self, portfolio: UpdatedPortfolio) -> List[str]:
        """Check if any position exceeds size limit"""
        violations = []

        if portfolio.total_value == 0:
            return violations

        for key, position in portfolio.positions.items():
            if position.market_value:
                position_pct = (position.market_value / portfolio.total_value) * 100

                if position_pct > self.max_position_size_pct:
                    violations.append(
                        f"Position size violation: {position.ticker} on "
                        f"{position.broker.value} = {position_pct:.1f}% "
                        f"(limit: {self.max_position_size_pct}%)"
                    )

        return violations

    def _check_broker_allocations(self, portfolio: UpdatedPortfolio) -> List[str]:
        """Check if any broker allocation exceeds limit"""
        violations = []

        if portfolio.total_value == 0:
            return violations

        for broker in set(pos.broker for pos in portfolio.positions.values()):
            broker_positions = portfolio.get_positions_by_broker(broker)
            broker_value = sum(
                pos.market_value for pos in broker_positions
                if pos.market_value
            )
            broker_pct = (broker_value / portfolio.total_value) * 100

            if broker_pct > self.max_broker_allocation_pct:
                violations.append(
                    f"Broker allocation violation: {broker.value} = {broker_pct:.1f}% "
                    f"(limit: {self.max_broker_allocation_pct}%)"
                )

        return violations

    def _check_leverage(self, portfolio: UpdatedPortfolio) -> List[str]:
        """Check portfolio leverage"""
        violations = []

        # V1: Placeholder - assume no leverage for now
        # Future: Calculate actual leverage from margin positions

        return violations

    def _generate_rebalance_signals(
        self,
        portfolio: UpdatedPortfolio,
        violations: List[str]
    ) -> List[TradingSignal]:
        """
        Generate signals to rebalance portfolio
        V1: Placeholder - return empty list
        Future: Smart rebalancing algorithm
        """
        # V1: Return empty list
        # Future: Analyze violations and generate appropriate signals to rebalance
        rebalance_signals = []

        # TODO: Implement rebalancing logic
        # For example:
        # - If position too large, generate SELL signal to reduce
        # - If broker allocation too high, generate signals to move to other brokers
        # - If leverage too high, generate signals to close positions

        return rebalance_signals
