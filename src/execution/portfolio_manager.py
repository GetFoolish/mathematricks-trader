#!/usr/bin/env python3
"""
Portfolio Manager for Mathematricks Trader
Aggregates positions across all brokers and manages portfolio state
"""

from typing import List, Dict
from datetime import datetime
from ..core.portfolio import (
    CurrentPortfolio, Position, Broker, PortfolioSummary
)
from ..brokers import BaseBroker


class PortfolioManager:
    """
    Manage portfolio across multiple brokers
    """

    def __init__(self, brokers: Dict[Broker, BaseBroker]):
        """
        Initialize portfolio manager

        Args:
            brokers: Dictionary of broker instances {Broker: BaseBroker}
        """
        self.brokers = brokers
        self.current_portfolio = CurrentPortfolio()

    def refresh_portfolio(self) -> CurrentPortfolio:
        """
        Refresh current portfolio from all brokers

        Returns:
            Updated CurrentPortfolio
        """
        print("🔄 Refreshing portfolio from all brokers...")

        # Reset portfolio
        self.current_portfolio = CurrentPortfolio()

        # Fetch positions from each broker
        for broker_type, broker in self.brokers.items():
            if not broker.is_connected:
                print(f"⚠️  {broker_type.value} not connected, skipping...")
                continue

            try:
                # Get positions
                positions = broker.get_positions()
                for position in positions:
                    self.current_portfolio.add_position(position)

                # Get cash balance
                balance = broker.get_account_balance()
                for currency, amount in balance.items():
                    self.current_portfolio.cash_by_broker[broker_type] = amount

                print(f"✅ {broker_type.value}: {len(positions)} positions, "
                      f"${amount:,.2f} cash")

            except Exception as e:
                print(f"❌ Error fetching from {broker_type.value}: {e}")

        self.current_portfolio.last_updated = datetime.now()

        print(f"📊 Total portfolio value: ${self.current_portfolio.total_value:,.2f}")
        print(f"📈 Total positions: {len(self.current_portfolio.positions)}")

        return self.current_portfolio

    def get_portfolio_summary(self) -> PortfolioSummary:
        """
        Get portfolio summary statistics

        Returns:
            PortfolioSummary object
        """
        return PortfolioSummary.from_portfolio(self.current_portfolio)

    def get_broker_allocation(self) -> Dict[str, float]:
        """
        Calculate percentage allocation by broker

        Returns:
            Dictionary of {broker: allocation_pct}
        """
        if self.current_portfolio.total_value == 0:
            return {}

        allocations = {}

        for broker in set(pos.broker for pos in self.current_portfolio.positions.values()):
            broker_positions = self.current_portfolio.get_positions_by_broker(broker)
            broker_value = sum(
                pos.market_value for pos in broker_positions
                if pos.market_value
            )
            allocations[broker.value] = (broker_value / self.current_portfolio.total_value) * 100

        return allocations

    def get_asset_allocation(self) -> Dict[str, float]:
        """
        Calculate percentage allocation by asset type

        Returns:
            Dictionary of {asset_type: allocation_pct}
        """
        if self.current_portfolio.total_value == 0:
            return {}

        allocations = {}

        for asset_type in set(pos.asset_type for pos in self.current_portfolio.positions.values()):
            asset_positions = [
                pos for pos in self.current_portfolio.positions.values()
                if pos.asset_type == asset_type
            ]
            asset_value = sum(
                pos.market_value for pos in asset_positions
                if pos.market_value
            )
            allocations[asset_type.value] = (asset_value / self.current_portfolio.total_value) * 100

        return allocations

    def connect_all_brokers(self) -> Dict[Broker, bool]:
        """
        Connect to all brokers

        Returns:
            Dictionary of {Broker: connection_status}
        """
        results = {}

        for broker_type, broker in self.brokers.items():
            try:
                success = broker.connect()
                results[broker_type] = success
            except Exception as e:
                print(f"❌ Failed to connect to {broker_type.value}: {e}")
                results[broker_type] = False

        return results

    def disconnect_all_brokers(self):
        """Disconnect from all brokers"""
        for broker_type, broker in self.brokers.items():
            try:
                broker.disconnect()
            except Exception as e:
                print(f"⚠️  Error disconnecting from {broker_type.value}: {e}")
