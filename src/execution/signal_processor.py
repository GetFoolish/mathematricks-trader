#!/usr/bin/env python3
"""
Signal Processor for Mathematricks Trader
Main execution engine that processes signals and routes to brokers
"""

from typing import Dict, List, Optional
from datetime import datetime
from ..core.signal_types import TradingSignal
from ..core.portfolio import (
    CurrentPortfolio, IdealPortfolio, UpdatedPortfolio,
    Position, Broker
)
from ..risk_management import RiskCalculator, ComplianceChecker
from ..order_management import SignalConverter, MathematricksOrder
from ..brokers import BaseBroker
from .portfolio_manager import PortfolioManager

# Global signal processor instance
_global_signal_processor: Optional['SignalProcessor'] = None


def set_signal_processor(processor: 'SignalProcessor'):
    """Set the global signal processor instance"""
    global _global_signal_processor
    _global_signal_processor = processor


def get_signal_processor() -> Optional['SignalProcessor']:
    """Get the global signal processor instance"""
    return _global_signal_processor


class SignalProcessor:
    """
    Process trading signals and execute orders
    Main orchestrator for the trading system
    """

    def __init__(
        self,
        portfolio_manager: PortfolioManager,
        risk_calculator: RiskCalculator,
        compliance_checker: ComplianceChecker,
        signal_converter: SignalConverter,
        data_store=None
    ):
        """
        Initialize signal processor

        Args:
            portfolio_manager: Portfolio manager instance
            risk_calculator: Risk calculator instance
            compliance_checker: Compliance checker instance
            signal_converter: Signal converter instance
            data_store: MongoDB data store (optional)
        """
        self.portfolio_manager = portfolio_manager
        self.risk_calculator = risk_calculator
        self.compliance_checker = compliance_checker
        self.signal_converter = signal_converter
        self.data_store = data_store

    def process_new_signal(self, signal_data: Dict) -> Dict:
        """
        Process a new signal from signal_collector
        This is the main entry point called by signal_collector.py

        Args:
            signal_data: Raw signal data from webhook

        Returns:
            Processing result dictionary
        """
        print("\n" + "="*80)
        print("🚀 PROCESSING NEW SIGNAL")
        print("="*80)

        try:
            # 1. Parse signal
            signal = TradingSignal.from_webhook(signal_data)
            print(f"📨 Signal ID: {signal.signalID}")
            print(f"📊 Strategy: {signal.strategy_name}")
            print(f"🔖 Type: {signal.signal_type.value}")

            # 2. Get current portfolio
            print("\n📂 Step 1: Fetching current portfolio...")
            current_portfolio = self.portfolio_manager.refresh_portfolio()

            # 3. Calculate ideal portfolio (risk-adjusted)
            print("\n⚖️  Step 2: Calculating ideal portfolio (risk-adjusted)...")
            ideal_portfolio = self.risk_calculator.adjust_portfolio(current_portfolio)
            print(f"   Risk Score: {ideal_portfolio.risk_score:.2f}/100")
            if ideal_portfolio.adjustments_made:
                print(f"   Adjustments: {len(ideal_portfolio.adjustments_made)}")

            # 4. Convert signal to orders
            print("\n🔄 Step 3: Converting signal to orders...")
            broker = self._determine_broker(signal)
            orders = self.signal_converter.convert_signal(signal, broker)
            print(f"   Generated {len(orders)} order(s)")

            # 5. Calculate updated portfolio (after signal)
            print("\n📈 Step 4: Calculating updated portfolio...")
            new_positions = self._simulate_positions_from_orders(orders)
            updated_portfolio = UpdatedPortfolio.from_current_with_signal(
                current_portfolio,
                new_positions,
                signal.signalID,
                signal.strategy_name
            )

            # 6. Check compliance
            print("\n🔍 Step 5: Checking compliance...")
            is_compliant, rebalance_signals = self.compliance_checker.check_compliance(
                updated_portfolio
            )

            if is_compliant:
                print("   ✅ Portfolio is compliant")
            else:
                print("   ⚠️  Compliance violations detected")
                # TODO: Handle rebalancing in future versions

            # 7. Execute orders (if compliant)
            execution_results = []

            if is_compliant:
                print("\n📤 Step 6: Executing orders...")
                for order in orders:
                    result = self._execute_order(order, broker)
                    execution_results.append(result)

                    # Store order in database
                    if self.data_store:
                        self.data_store.store_order(order, result)

            else:
                print("\n⛔ Step 6: Skipping execution (not compliant)")

            # 8. Store signal in database
            if self.data_store:
                self.data_store.store_signal(signal, execution_results)

            print("\n✅ SIGNAL PROCESSING COMPLETE")
            print("="*80 + "\n")

            return {
                'success': True,
                'signal_id': signal.signalID,
                'orders_generated': len(orders),
                'orders_executed': len(execution_results),
                'is_compliant': is_compliant,
                'execution_results': execution_results
            }

        except Exception as e:
            print(f"\n❌ ERROR PROCESSING SIGNAL: {e}")
            print("="*80 + "\n")

            return {
                'success': False,
                'error': str(e)
            }

    def _determine_broker(self, signal: TradingSignal) -> Broker:
        """
        Determine which broker to use for this signal
        V1: Simple logic based on asset type
        Future: Smart routing, best execution, etc.
        """
        # Simple mapping for V1
        # Can be enhanced with strategy-specific broker preferences

        asset_type = None

        if hasattr(signal.signal, 'ticker'):
            ticker = signal.signal.ticker.upper()

            # Crypto -> Binance
            if ticker in ['BTC', 'ETH', 'BNB', 'SOL']:
                return Broker.BINANCE

            # Indian stocks -> Zerodha
            if ticker in ['RELIANCE', 'TCS', 'INFY']:
                return Broker.ZERODHA

            # Forex -> Vantage
            if '/' in ticker or ticker in ['EUR', 'GBP', 'JPY']:
                return Broker.VANTAGE

        # Default to IBKR
        return Broker.IBKR

    def _simulate_positions_from_orders(
        self,
        orders: List[MathematricksOrder]
    ) -> List[Position]:
        """
        Simulate positions that would result from orders
        Used for compliance checking before execution
        """
        positions = []

        for order in orders:
            # Create hypothetical position
            position = Position(
                ticker=order.ticker,
                broker=order.broker,
                asset_type=order.asset_type,
                quantity=order.quantity if order.order_side.value == 'buy' else -order.quantity,
                avg_price=order.limit_price or 0.0,
                current_price=order.limit_price or 0.0
            )
            positions.append(position)

        return positions

    def _execute_order(
        self,
        order: MathematricksOrder,
        broker_type: Broker
    ) -> Dict:
        """Execute a single order through the broker"""
        broker = self.portfolio_manager.brokers.get(broker_type)

        if not broker or not broker.is_connected:
            print(f"   ❌ {broker_type.value} not available")
            return {
                'order_id': order.signal_id,
                'status': 'failed',
                'error': f'{broker_type.value} not connected'
            }

        try:
            # Send order to broker
            confirmation = broker.send_order(order)

            print(f"   ✅ {broker_type.value}: {confirmation.message}")

            return {
                'order_id': confirmation.order_id,
                'broker_order_id': confirmation.broker_order_id,
                'status': confirmation.status.value,
                'message': confirmation.message
            }

        except Exception as e:
            print(f"   ❌ {broker_type.value} error: {e}")

            return {
                'order_id': order.signal_id,
                'status': 'failed',
                'error': str(e)
            }
