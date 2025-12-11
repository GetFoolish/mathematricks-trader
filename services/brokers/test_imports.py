#!/usr/bin/env python3
"""
Quick test to verify broker library imports work correctly
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing broker library imports...")

try:
    # Test base imports
    print("1. Testing base imports...")
    from base import AbstractBroker, OrderSide, OrderType, OrderStatus
    print("   ✓ base.py imports successful")

    # Test exception imports
    print("2. Testing exception imports...")
    from exceptions import (
        BrokerError,
        BrokerConnectionError,
        OrderRejectedError,
        OrderNotFoundError,
        BrokerAPIError
    )
    print("   ✓ exceptions.py imports successful")

    # Test IBKR imports
    print("3. Testing IBKR imports...")
    from ibkr import IBKRBroker
    print("   ✓ IBKR broker imports successful")

    # Test Zerodha imports
    print("4. Testing Zerodha imports...")
    try:
        from zerodha import ZerodhaBroker
        print("   ✓ Zerodha broker imports successful")
    except ImportError as e:
        print(f"   ⚠  Zerodha import warning (kiteconnect not installed): {e}")

    # Test factory imports
    print("5. Testing factory imports...")
    from factory import BrokerFactory, create_broker_from_env
    print("   ✓ Factory imports successful")

    # Test package-level imports
    print("6. Testing package-level imports...")
    import brokers
    print(f"   ✓ Package imports successful (version {brokers.__version__})")

    # Test BrokerFactory.get_supported_brokers()
    print("7. Testing factory methods...")
    supported = BrokerFactory.get_supported_brokers()
    print(f"   ✓ Supported brokers: {supported}")

    # Test creating broker instances (without connecting)
    print("8. Testing broker instantiation...")

    # Test IBKR broker creation
    ibkr_config = {
        "broker": "IBKR",
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 999,  # Using 999 to avoid conflicts with running services
        "account_id": "TEST"
    }
    ibkr_broker = BrokerFactory.create_broker(ibkr_config)
    print(f"   ✓ IBKR broker created: {ibkr_broker.broker_name}")

    print("\n✅ ALL TESTS PASSED!")
    print("\nBroker library is ready to use.")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
