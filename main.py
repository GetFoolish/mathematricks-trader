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

# Load environment variables
load_dotenv()


def initialize_brokers():
    """Initialize all broker instances"""
    print("🔧 Initializing brokers...")

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
    print("="*80)
    print("🚀 MATHEMATRICKS TRADER V1 - INITIALIZATION")
    print("="*80)

    # 1. Initialize brokers
    brokers = initialize_brokers()

    # 2. Initialize portfolio manager
    print("\n📊 Initializing portfolio manager...")
    portfolio_manager = PortfolioManager(brokers)

    # 3. Connect to brokers
    print("\n🔌 Connecting to brokers...")
    connection_results = portfolio_manager.connect_all_brokers()

    for broker, success in connection_results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {broker.value}")

    # 4. Initialize risk management
    print("\n⚖️  Initializing risk management...")
    risk_config = {
        'max_position_size_pct': float(os.getenv('MAX_POSITION_SIZE_PCT', '10')),
        'max_broker_allocation_pct': float(os.getenv('MAX_BROKER_ALLOCATION_PCT', '40'))
    }
    risk_calculator = RiskCalculator(risk_config)
    compliance_checker = ComplianceChecker(risk_config)

    # 5. Initialize signal converter
    print("\n🔄 Initializing signal converter...")
    signal_converter = SignalConverter()

    # 6. Initialize data store
    print("\n💾 Initializing MongoDB data store...")
    mongodb_url = os.getenv('mongodbconnectionstring')
    data_store = DataStore(mongodb_url)
    data_store.connect()

    # 7. Initialize signal processor
    print("\n⚡ Initializing signal processor...")
    signal_processor = SignalProcessor(
        portfolio_manager=portfolio_manager,
        risk_calculator=risk_calculator,
        compliance_checker=compliance_checker,
        signal_converter=signal_converter,
        data_store=data_store
    )

    # Set global signal processor
    set_signal_processor(signal_processor)

    print("\n" + "="*80)
    print("✅ MATHEMATRICKS TRADER V1 - READY")
    print("="*80)

    return signal_processor


def main():
    """Main entry point"""
    # Initialize trading system
    signal_processor = initialize_trading_system()

    print("\n📡 System is now listening for signals from signal_collector.py")
    print("   Signals will be automatically processed when received.\n")

    print("🎨 To view the dashboard, run:")
    print("   streamlit run frontend/app.py\n")

    print("📝 Signal collector should be running separately:")
    print("   python signal_collector.py\n")

    # Keep the process running
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down Mathematricks Trader...")
        # Cleanup
        if signal_processor:
            signal_processor.portfolio_manager.disconnect_all_brokers()
            if signal_processor.data_store:
                signal_processor.data_store.disconnect()
        print("✅ Shutdown complete\n")


if __name__ == "__main__":
    main()
