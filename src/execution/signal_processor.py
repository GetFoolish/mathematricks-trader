#!/usr/bin/env python3
"""
Signal Processor for Mathematricks Trader
Main execution engine that processes signals and routes to brokers

NOTE: Modified to bridge signals to new MVP microservices (Cerebro + Execution)
"""

from typing import Dict, List, Optional
from datetime import datetime
import os
import json
from ..core.signal_types import TradingSignal
from ..core.portfolio import (
    CurrentPortfolio, IdealPortfolio, UpdatedPortfolio,
    Position, Broker
)
from ..risk_management import RiskCalculator, ComplianceChecker
from ..order_management import SignalConverter, MathematricksOrder
from ..brokers import BaseBroker
from .portfolio_manager import PortfolioManager
from ..utils.logger import setup_logger
from telegram import TelegramNotifier

# Setup logger
logger = setup_logger('signal_processor', 'signal_processor.log')

# Try to import Pub/Sub (optional - falls back to old logic if not available)
try:
    from google.cloud import pubsub_v1
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False
    logger.info("Google Cloud Pub/Sub not available - using legacy processing")

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
        data_store=None,
        telegram_notifier: TelegramNotifier = None
    ):
        """
        Initialize signal processor

        Args:
            portfolio_manager: Portfolio manager instance
            risk_calculator: Risk calculator instance
            compliance_checker: Compliance checker instance
            signal_converter: Signal converter instance
            data_store: MongoDB data store (optional)
            telegram_notifier: Telegram notifier (optional)
        """
        self.portfolio_manager = portfolio_manager
        self.risk_calculator = risk_calculator
        self.compliance_checker = compliance_checker
        self.signal_converter = signal_converter
        self.data_store = data_store
        self.telegram = telegram_notifier or TelegramNotifier()

        # Initialize Pub/Sub publisher if available
        self.pubsub_publisher = None
        self.pubsub_topic_path = None
        if PUBSUB_AVAILABLE:
            try:
                project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
                self.pubsub_publisher = pubsub_v1.PublisherClient()
                self.pubsub_topic_path = self.pubsub_publisher.topic_path(project_id, 'standardized-signals')
                logger.info("✅ Pub/Sub bridge enabled - signals will route to microservices")
            except Exception as e:
                logger.info(f"⚠️  Pub/Sub initialization failed: {e} - using legacy processing")
                self.pubsub_publisher = None

    def _send_to_cerebro_microservice(self, signal_data: Dict) -> bool:
        """
        Send signal to Cerebro microservice via Pub/Sub
        Returns True if successfully published, False otherwise
        """
        if not self.pubsub_publisher or not self.pubsub_topic_path:
            return False

        try:
            # Convert signal data to standardized format for Cerebro
            standardized_signal = {
                "signal_id": f"SC_{datetime.utcnow().timestamp()}",
                "strategy_id": signal_data.get('strategy_name', 'Unknown'),
                "timestamp": signal_data.get('timestamp', datetime.utcnow().isoformat()),
                "instrument": signal_data.get('signal', {}).get('ticker', ''),
                "direction": "LONG",  # Simplified - would parse from signal
                "action": signal_data.get('signal', {}).get('action', 'ENTRY').upper(),
                "order_type": signal_data.get('signal', {}).get('order_type', 'MARKET').upper(),
                "price": float(signal_data.get('signal', {}).get('price', 0)),
                "quantity": float(signal_data.get('signal', {}).get('quantity', 1)),
                "stop_loss": float(signal_data.get('signal', {}).get('stop_loss', 0)),
                "take_profit": float(signal_data.get('signal', {}).get('take_profit', 0)),
                "expiry": None,
                "metadata": {
                    "expected_alpha": 0.02,  # Would come from backtest data
                    "original_signal": signal_data
                },
                "processed_by_cerebro": False,
                "created_at": datetime.utcnow().isoformat()
            }

            # Publish to Pub/Sub
            message_data = json.dumps(standardized_signal).encode('utf-8')
            future = self.pubsub_publisher.publish(self.pubsub_topic_path, message_data)
            message_id = future.result(timeout=5.0)

            logger.info(f"✅ Signal published to Cerebro microservice: {message_id}")
            logger.info(f"   → Signal ID: {standardized_signal['signal_id']}")
            logger.info(f"   → Instrument: {standardized_signal['instrument']}")
            logger.info(f"   → Action: {standardized_signal['action']}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish to Cerebro microservice: {e}")
            return False

    def process_new_signal(self, signal_data: Dict) -> Dict:
        """
        Process a new signal from signal_collector
        This is the main entry point called by signal_collector.py

        Args:
            signal_data: Raw signal data from webhook

        Returns:
            Processing result dictionary
        """
        logger.info("="*80)
        logger.info("🔥 PROCESSING NEW SIGNAL")
        logger.info("="*80)

        # Try microservices path first (if Pub/Sub available)
        if self.pubsub_publisher:
            logger.info("🚀 Routing to MVP microservices (Cerebro → Execution)")
            logger.info(f"   Strategy: {signal_data.get('strategy_name', 'Unknown')}")
            logger.info(f"   Signal: {signal_data.get('signal', {})}")

            if self._send_to_cerebro_microservice(signal_data):
                logger.info("="*80)
                return {
                    'success': True,
                    'message': 'Signal routed to microservices',
                    'mode': 'microservices',
                    'signal_id': signal_data.get('signalID')
                }
            else:
                logger.warning("⚠️  Microservices routing failed - falling back to legacy processing")

        # Legacy processing path (original V1 logic)
        logger.info("📊 Using legacy processing (V1)")
        try:
            # 1. Parse signal
            signal = TradingSignal.from_webhook(signal_data)
            logger.info(f"Signal ID: {signal.signalID}")
            logger.info(f"Strategy: {signal.strategy_name}")
            logger.info(f"Type: {signal.signal_type.value}")

            # Send Telegram notification: Signal received
            self.telegram.notify_signal_received(signal_data)

            # 2. Get current portfolio
            logger.info("Step 1: Fetching current portfolio...")
            current_portfolio = self.portfolio_manager.refresh_portfolio()

            # 3. Calculate ideal portfolio (risk-adjusted)
            logger.info("Step 2: Calculating ideal portfolio (risk-adjusted)...")
            ideal_portfolio = self.risk_calculator.adjust_portfolio(current_portfolio)
            logger.info(f"Risk Score: {ideal_portfolio.risk_score:.2f}/100")
            if ideal_portfolio.adjustments_made:
                logger.info(f"Adjustments: {len(ideal_portfolio.adjustments_made)}")

            # 4. Convert signal to orders
            logger.info("Step 3: Converting signal to orders...")
            broker = self._determine_broker(signal)
            orders = self.signal_converter.convert_signal(signal, broker)
            logger.info(f"Generated {len(orders)} order(s)")

            # 5. Calculate updated portfolio (after signal)
            logger.info("Step 4: Calculating updated portfolio...")
            new_positions = self._simulate_positions_from_orders(orders)
            updated_portfolio = UpdatedPortfolio.from_current_with_signal(
                current_portfolio,
                new_positions,
                signal.signalID,
                signal.strategy_name
            )

            # 6. Check compliance
            logger.info("Step 5: Checking compliance...")
            is_compliant, rebalance_signals = self.compliance_checker.check_compliance(
                updated_portfolio
            )

            if is_compliant:
                logger.info("✅ Portfolio is compliant")
            else:
                logger.warning("⚠️  Compliance violations detected")
                # Send Telegram notification: Compliance violation
                self.telegram.notify_compliance_violation(
                    signal.signalID,
                    signal.strategy_name,
                    [str(v) for v in rebalance_signals] if rebalance_signals else ["Portfolio compliance check failed"]
                )
                # TODO: Handle rebalancing in future versions

            # 7. Execute orders (if compliant)
            execution_results = []

            if is_compliant:
                logger.info("Step 6: Executing orders...")
                for order in orders:
                    result = self._execute_order(order, broker)
                    execution_results.append(result)

                    # Store order in database
                    if self.data_store:
                        self.data_store.store_order(order, result)

                # Send Telegram notification: Trades executed
                orders_dict = [order.to_dict() for order in orders]
                self.telegram.notify_trade_executed(
                    signal.signalID,
                    signal.strategy_name,
                    orders_dict,
                    execution_results
                )

            else:
                logger.warning("Step 6: Skipping execution (not compliant)")

            # 8. Store signal in database
            if self.data_store:
                self.data_store.store_signal(signal, execution_results)

            logger.info("SIGNAL PROCESSING COMPLETE")
            logger.info("="*80)

            return {
                'success': True,
                'signal_id': signal.signalID,
                'orders_generated': len(orders),
                'orders_executed': len(execution_results),
                'is_compliant': is_compliant,
                'execution_results': execution_results
            }

        except Exception as e:
            logger.error(f"ERROR PROCESSING SIGNAL: {e}", exc_info=True)
            logger.info("="*80)

            # Send Telegram notification: Signal failed
            try:
                signal_id = signal_data.get('signalID', 'Unknown')
                strategy_name = signal_data.get('strategy_name', 'Unknown')
                self.telegram.notify_signal_failed(signal_id, strategy_name, str(e))
            except:
                pass  # Don't let Telegram errors break the error handling

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
            logger.error(f"{broker_type.value} not available")
            return {
                'order_id': order.signal_id,
                'status': 'failed',
                'error': f'{broker_type.value} not connected'
            }

        try:
            # Send order to broker
            confirmation = broker.send_order(order)

            logger.info(f"✅ {broker_type.value}: {confirmation.message}")

            return {
                'order_id': confirmation.order_id,
                'broker_order_id': confirmation.broker_order_id,
                'status': confirmation.status.value,
                'message': confirmation.message
            }

        except Exception as e:
            logger.error(f"{broker_type.value} error: {e}", exc_info=True)

            return {
                'order_id': order.signal_id,
                'status': 'failed',
                'error': str(e)
            }
