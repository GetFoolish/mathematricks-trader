#!/usr/bin/env python3
"""
Test 1: Send a Telegram message
Tests the Telegram notification system
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telegram import TelegramNotifier
from src.utils.logger import setup_logger

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger('test_telegram', 'test_telegram.log')


def test_telegram_message():
    """Test sending a Telegram message"""
    logger.info("=" * 80)
    logger.info("TEST 1: TELEGRAM MESSAGE")
    logger.info("=" * 80)

    # Initialize Telegram notifier (uses .env variables)
    telegram = TelegramNotifier()

    if not telegram.enabled:
        logger.error("❌ Telegram is not enabled!")
        logger.error("Please check your .env file:")
        logger.error("  - TELEGRAM_ENABLED=true")
        logger.error("  - TELEGRAM_BOT_TOKEN=<your_token>")
        logger.error("  - TELEGRAM_CHAT_ID=<your_chat_id>")
        return False

    logger.info("Telegram is enabled. Sending test message...")

    # Send a simple test message
    test_message = """
🧪 <b>TEST MESSAGE</b>

This is a test message from Mathematricks Trader V1.

✅ If you're seeing this, Telegram notifications are working!

🕐 <i>Test completed successfully</i>
"""

    success = telegram.send_message(test_message)

    if success:
        logger.info("✅ Test message sent successfully!")
        logger.info("Check your Telegram to see the message.")
        return True
    else:
        logger.error("❌ Failed to send test message")
        return False


def test_all_notification_types():
    """Test all notification types"""
    logger.info("\nTesting all notification types...")

    telegram = TelegramNotifier()

    if not telegram.enabled:
        logger.error("Telegram not enabled, skipping notification tests")
        return False

    # Test signal received
    logger.info("1. Testing signal received notification...")
    signal_data = {
        'signalID': 'TEST_001',
        'strategy_name': 'Test Strategy',
        'timestamp': '2025-01-01 10:00:00',
        'signal': {
            'ticker': 'AAPL',
            'action': 'BUY',
            'price': 150.25
        }
    }
    telegram.notify_signal_received(signal_data)

    # Test trade executed
    logger.info("2. Testing trade executed notification...")
    orders = [
        {
            'ticker': 'AAPL',
            'order_side': 'BUY',
            'quantity': 100,
            'broker': 'IBKR'
        }
    ]
    execution_results = [
        {
            'status': 'submitted',
            'order_id': 'TEST_ORDER_001'
        }
    ]
    telegram.notify_trade_executed('TEST_001', 'Test Strategy', orders, execution_results)

    logger.info("✅ All notification tests sent!")
    logger.info("Check your Telegram to verify all messages arrived.")

    return True


if __name__ == "__main__":
    logger.info("\nStarting Telegram tests...\n")

    # Test 1: Simple message
    success1 = test_telegram_message()

    # Test 2: All notification types
    success2 = test_all_notification_types()

    logger.info("\n" + "=" * 80)
    if success1 and success2:
        logger.info("✅ ALL TELEGRAM TESTS PASSED")
    else:
        logger.info("❌ SOME TESTS FAILED")
    logger.info("=" * 80)
