#!/usr/bin/env python3
"""
Mathematricks Trader V1
Main entry point to initialize and start the trading system
"""

import os
from dotenv import load_dotenv
from src.core.portfolio import Broker
from src.brokers import IBKRBroker, ZerodhaBroker, BinanceBroker, VantageBroker
from src.execution import PortfolioManager, SignalProcessor
from src.execution.signal_processor import set_signal_processor
from src.risk_management import RiskCalculator, ComplianceChecker
from src.order_management import SignalConverter
from src.reporting import DataStore
from src.utils.logger import setup_logger
from telegram import TelegramNotifier

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger('main', 'main.log')


def initialize_brokers():
    """Initialize all broker instances"""
    logger.info("Initializing brokers...")

    brokers = {}

    # IBKR
    ibkr_config = {
        'client_id': os.getenv('IBKR_CLIENT_ID'),
        'api_key': os.getenv('IBKR_API_KEY'),
        'api_secret': os.getenv('IBKR_API_SECRET'),
        'paper_trading': os.getenv('IBKR_PAPER_TRADING', 'true').lower() == 'true'
    }
    brokers[Broker.IBKR] = IBKRBroker(ibkr_config)

    # Zerodha
    zerodha_config = {
        'api_key': os.getenv('ZERODHA_API_KEY'),
        'api_secret': os.getenv('ZERODHA_API_SECRET'),
        'access_token': os.getenv('ZERODHA_ACCESS_TOKEN')
    }
    brokers[Broker.ZERODHA] = ZerodhaBroker(zerodha_config)

    # Binance
    binance_config = {
        'api_key': os.getenv('BINANCE_API_KEY'),
        'api_secret': os.getenv('BINANCE_API_SECRET'),
        'testnet': os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
    }
    brokers[Broker.BINANCE] = BinanceBroker(binance_config)

    # Vantage
    vantage_config = {
        'api_key': os.getenv('VANTAGE_API_KEY'),
        'api_secret': os.getenv('VANTAGE_API_SECRET'),
        'account_id': os.getenv('VANTAGE_ACCOUNT_ID'),
        'demo': os.getenv('VANTAGE_DEMO', 'true').lower() == 'true'
    }
    brokers[Broker.VANTAGE] = VantageBroker(vantage_config)

    return brokers


def initialize_trading_system():
    """Initialize the complete trading system"""
    logger.info("="*80)
    logger.info("MATHEMATRICKS TRADER V1 - INITIALIZATION")
    logger.info("="*80)

    # 1. Initialize brokers
    brokers = initialize_brokers()

    # 2. Initialize portfolio manager
    logger.info("Initializing portfolio manager...")
    portfolio_manager = PortfolioManager(brokers)

    # 3. Connect to brokers
    logger.info("Connecting to brokers...")
    connection_results = portfolio_manager.connect_all_brokers()

    for broker, success in connection_results.items():
        if success:
            logger.info(f"✅ Connected to {broker.value}")
        else:
            logger.error(f"❌ Failed to connect to {broker.value}")

    # 4. Initialize risk management
    logger.info("Initializing risk management...")
    risk_config = {
        'max_position_size_pct': float(os.getenv('MAX_POSITION_SIZE_PCT', '10')),
        'max_broker_allocation_pct': float(os.getenv('MAX_BROKER_ALLOCATION_PCT', '40'))
    }
    risk_calculator = RiskCalculator(risk_config)
    compliance_checker = ComplianceChecker(risk_config)

    # 5. Initialize signal converter
    logger.info("Initializing signal converter...")
    signal_converter = SignalConverter()

    # 6. Initialize data store
    logger.info("Initializing MongoDB data store...")
    mongodb_url = os.getenv('mongodbconnectionstring')
    data_store = DataStore(mongodb_url)
    data_store.connect()

    # 7. Initialize Telegram notifier
    logger.info("Initializing Telegram notifier...")
    telegram = TelegramNotifier()

    # 8. Initialize signal processor
    logger.info("Initializing signal processor...")
    signal_processor = SignalProcessor(
        portfolio_manager=portfolio_manager,
        risk_calculator=risk_calculator,
        compliance_checker=compliance_checker,
        signal_converter=signal_converter,
        data_store=data_store,
        telegram_notifier=telegram
    )

    # Set global signal processor
    set_signal_processor(signal_processor)

    logger.info("="*80)
    logger.info("MATHEMATRICKS TRADER V1 - READY")
    logger.info("="*80)

    return signal_processor


def main():
    """Main entry point"""
    # Initialize trading system
    signal_processor = initialize_trading_system()

    logger.info("System is now listening for signals from signal_collector.py")
    logger.info("Signals will be automatically processed when received")
    logger.info("View dashboard at: http://localhost:8501")

    # Keep the process running
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Mathematricks Trader...")
        # Cleanup
        if signal_processor:
            signal_processor.portfolio_manager.disconnect_all_brokers()
            if signal_processor.data_store:
                signal_processor.data_store.disconnect()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
