#!/usr/bin/env python3
"""
Test 3: Random Signal Generator
Sends random signals to the system at random intervals (2-10 seconds)
Runs continuously until Ctrl+C
"""

import os
import sys
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.execution.signal_processor import get_signal_processor
from src.utils.logger import setup_logger

# Load environment variables
load_dotenv()

# Setup logger
logger = setup_logger('test_random_signals', 'test_random_signals.log')

# Ticker list for random selection
TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
    'META', 'NVDA', 'AMD', 'NFLX', 'DIS',
    'SPY', 'QQQ', 'IWM', 'TLT', 'GLD',
    'RELIANCE', 'TCS', 'INFY',  # Indian stocks
    'BTC', 'ETH', 'SOL',  # Crypto
    'EURUSD', 'GBPUSD', 'USDJPY'  # Forex
]

# Actions
ACTIONS = ['BUY', 'SELL']

# Strategy names
STRATEGIES = [
    'Momentum_Strategy_1',
    'Mean_Reversion_Strategy_2',
    'Breakout_Strategy_3',
    'Trend_Following_Strategy_4',
    'Statistical_Arbitrage_5'
]


def generate_random_signal():
    """Generate a random trading signal"""
    ticker = random.choice(TICKERS)
    action = random.choice(ACTIONS)
    strategy = random.choice(STRATEGIES)

    # Generate realistic price based on ticker type
    if ticker in ['BTC', 'ETH', 'SOL']:
        # Crypto prices
        base_prices = {'BTC': 45000, 'ETH': 2500, 'SOL': 100}
        price = base_prices.get(ticker, 1000) * random.uniform(0.95, 1.05)
    elif '/' in ticker or 'USD' in ticker:
        # Forex prices
        price = random.uniform(0.5, 2.0)
    else:
        # Stock prices
        price = random.uniform(50, 500)

    # Create signal in webhook format
    signal_data = {
        'signalID': f'TEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{random.randint(1000, 9999)}',
        'strategy_name': strategy,
        'timestamp': datetime.now().isoformat(),
        'signal_sent_EPOCH': int(time.time()),
        'signal': {
            'ticker': ticker,
            'action': action,
            'price': round(price, 2)
        }
    }

    return signal_data


def run_random_signal_generator():
    """Run the random signal generator"""
    logger.info("=" * 80)
    logger.info("TEST 3: RANDOM SIGNAL GENERATOR")
    logger.info("=" * 80)

    # Get signal processor
    logger.info("Getting signal processor...")
    signal_processor = get_signal_processor()

    if not signal_processor:
        logger.error("❌ Signal processor not initialized!")
        logger.error("\nPlease start the main trading system first:")
        logger.error("  python main.py")
        logger.error("\nThen run this test in a separate terminal.")
        return False

    logger.info("✅ Signal processor is ready")
    logger.info(f"\nTicker pool: {len(TICKERS)} tickers")
    logger.info(f"Strategies: {len(STRATEGIES)} strategies")
    logger.info("\nStarting random signal generation...")
    logger.info("Press Ctrl+C to stop\n")

    signal_count = 0

    try:
        while True:
            # Generate random signal
            signal_data = generate_random_signal()

            logger.info("-" * 80)
            logger.info(f"Signal #{signal_count + 1}")
            logger.info(f"  ID: {signal_data['signalID']}")
            logger.info(f"  Strategy: {signal_data['strategy_name']}")
            logger.info(f"  Ticker: {signal_data['signal']['ticker']}")
            logger.info(f"  Action: {signal_data['signal']['action']}")
            logger.info(f"  Price: ${signal_data['signal']['price']:.2f}")

            # Send signal to processor
            try:
                result = signal_processor.process_new_signal(signal_data)

                if result.get('success'):
                    logger.info(f"  ✅ Signal processed successfully")
                    logger.info(f"  Orders generated: {result.get('orders_generated', 0)}")
                    logger.info(f"  Orders executed: {result.get('orders_executed', 0)}")
                else:
                    logger.warning(f"  ⚠️  Signal processing failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                logger.error(f"  ❌ Error processing signal: {e}")

            signal_count += 1

            # Random wait between 2-10 seconds
            wait_time = random.uniform(2, 10)
            logger.info(f"  Waiting {wait_time:.1f} seconds until next signal...")

            time.sleep(wait_time)

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.info("🛑 STOPPED BY USER")
        logger.info(f"Total signals sent: {signal_count}")
        logger.info("=" * 80)
        return True


if __name__ == "__main__":
    logger.info("\nStarting random signal generator test...\n")
    logger.info("NOTE: Make sure the main trading system is running:")
    logger.info("  python main.py")
    logger.info("\nThis test will send signals to the running system.\n")

    time.sleep(2)  # Give user time to read

    success = run_random_signal_generator()

    if success:
        logger.info("\n✅ TEST COMPLETED")
    else:
        logger.info("\n❌ TEST FAILED")
