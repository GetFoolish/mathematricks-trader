#!/usr/bin/env python3
"""
Quick test to verify execution service handles instrument_type field correctly
Uses REAL strategies that currently have portfolio allocations
"""

import os
import time
import logging
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "https://staging.mathematricks.fund/api/signals"
PASSPHRASE = "yahoo123"
ACCOUNT = "DU1234567"


def send_signal(payload):
    """Send signal to API"""
    timestamp = datetime.now(timezone.utc)
    strategy = payload.get('strategy_id')

    signal = {
        'timestamp': timestamp.isoformat(),
        'signalID': f'{strategy}_{timestamp.strftime("%Y%m%d_%H%M%S")}_{int(timestamp.microsecond/1000):03d}',
        'signal_sent_EPOCH': int(timestamp.timestamp()),
        'strategy_name': strategy,
        'signal': payload,
        'environment': 'staging',
        'passphrase': PASSPHRASE
    }

    try:
        response = requests.post(API_URL, json=signal, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Signal sent: {signal['signalID']}")
            return True
        else:
            logger.error(f"❌ Failed: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


def main():
    logger.info("="*80)
    logger.info("Testing Multi-Asset Execution with Strategies that have Portfolio Allocations")
    logger.info("="*80)
    logger.info("")
    logger.info("Current Portfolio Allocations (from Cerebro logs):")
    logger.info("  - SPY: 6.54%")
    logger.info("  - Forex: 13.23%")
    logger.info("  - Com1-Met: 43.09%")
    logger.info("  - Com2-Ag: 10.38%")
    logger.info("  - SPX_1-D_Opt: 57.79%")
    logger.info("  - Com3-Mkt: 17.07%")
    logger.info("")

    # Test 1: SPY stock with instrument_type field
    logger.info("\n[Test 1] SPY - Stock (has 6.54% allocation)")
    send_signal({
        'strategy_id': 'SPY',
        'instrument': 'SPY',
        'instrument_type': 'STOCK',
        'direction': 'LONG',
        'action': 'BUY',
        'order_type': 'MARKET',
        'price': 575.25,
        'quantity': 10,
        'signal_type': 'ENTRY',
        'account': ACCOUNT
    })
    time.sleep(10)

    # Test 2: Forex with instrument_type field
    logger.info("\n[Test 2] Forex - EURUSD (has 13.23% allocation)")
    send_signal({
        'strategy_id': 'Forex',
        'instrument': 'EURUSD',
        'instrument_type': 'FOREX',
        'direction': 'LONG',
        'action': 'BUY',
        'order_type': 'MARKET',
        'price': 1.0850,
        'quantity': 100000,
        'signal_type': 'ENTRY',
        'account': ACCOUNT
    })
    time.sleep(10)

    # Test 3: Com1-Met Gold Future (has 43.09% allocation)
    logger.info("\n[Test 3] Com1-Met - Gold Future GC (has 43.09% allocation)")
    send_signal({
        'strategy_id': 'Com1-Met',
        'instrument': 'GC',
        'instrument_type': 'FUTURE',
        'expiry': '20250226',  # February 2025 contract (active contract month)
        'exchange': 'COMEX',
        'direction': 'LONG',
        'action': 'BUY',
        'order_type': 'MARKET',
        'price': 2650.00,
        'quantity': 5,
        'signal_type': 'ENTRY',
        'account': ACCOUNT
    })
    time.sleep(10)

    # Test 4: SPX_1-D_Opt - Option (has 57.79% allocation)
    logger.info("\n[Test 4] SPX_1-D_Opt - SPY Iron Condor (has 57.79% allocation)")
    send_signal({
        'strategy_id': 'SPX_1-D_Opt',
        'instrument_type': 'OPTION',
        'underlying': 'SPY',
        'legs': [
            {'strike': 570, 'expiry': '20251128', 'right': 'P', 'action': 'BUY', 'quantity': 1},
            {'strike': 575, 'expiry': '20251128', 'right': 'P', 'action': 'SELL', 'quantity': 1},
            {'strike': 585, 'expiry': '20251128', 'right': 'C', 'action': 'SELL', 'quantity': 1},
            {'strike': 590, 'expiry': '20251128', 'right': 'C', 'action': 'BUY', 'quantity': 1}
        ],
        'direction': 'LONG',
        'action': 'BUY',
        'order_type': 'MARKET',
        'price': 1.50,
        'quantity': 1,
        'signal_type': 'ENTRY',
        'account': ACCOUNT
    })
    time.sleep(10)

    logger.info("\n" + "="*80)
    logger.info("✅ All test signals sent!")
    logger.info("="*80)
    logger.info("\nCheck logs:")
    logger.info("  tail -f logs/signal_processing.log   # See signal journey")
    logger.info("  tail -f logs/cerebro_service.log     # See Cerebro approval/rejection")
    logger.info("  tail -f logs/execution_service.log   # See contract creation with instrument_type")


if __name__ == '__main__':
    main()
