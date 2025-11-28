#!/usr/bin/env python3
"""
Comprehensive Multi-Asset Signal Testing Script

Tests 4 signal patterns across 4 asset classes (16 total test scenarios):
- Equity (stocks)
- Options (single-leg and multi-leg strategies)
- Forex
- Futures

Patterns:
1. Simple entry → exit
2. Scale in (multiple entries) → full exit
3. Swing trading (LONG → SHORT → LONG)
4. Partial exits (entry → scale out → scale out → exit)
"""

import os
import sys
import time
import logging
import random
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any
from collections import defaultdict
import requests
from dotenv import load_dotenv

# Load environment
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveSignalTester:
    """Test signal patterns across multiple asset classes with shuffled execution"""

    def __init__(self, use_staging: bool = True):
        self.api_url = "https://staging.mathematricks.fund/api/signals" if use_staging else "https://mathematricks.fund/api/signals"
        self.account = "DU1234567"
        self.passphrase = "yahoo123"

    def send_signal(self, signal_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a signal to the API

        Returns:
            Dict with 'status' ('success' or 'failed') and optional 'error' message
        """
        timestamp = datetime.now(timezone.utc)
        strategy = signal_payload.get('strategy_id', 'TEST')

        signal = {
            'timestamp': timestamp.isoformat(),
            'signalID': f'{strategy}_{timestamp.strftime("%Y%m%d_%H%M%S")}_{int(timestamp.microsecond/1000):03d}',
            'signal_sent_EPOCH': int(timestamp.timestamp()),
            'strategy_name': strategy,
            'signal': signal_payload,
            'environment': 'staging',
            'passphrase': self.passphrase
        }

        try:
            response = requests.post(self.api_url, json=signal, timeout=10)
            signal_id = signal['signalID']

            if response.status_code == 200:
                logger.info(f"✅ Signal sent: {signal_id}")
                return {'status': 'success', 'signal_id': signal_id}
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_msg += f" - {response.json()}"
                except:
                    error_msg += f" - {response.text[:100]}"

                logger.error(f"❌ Signal rejected: {error_msg}")
                return {'status': 'failed', 'error': error_msg}

        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            logger.error(f"❌ {error_msg}")
            return {'status': 'failed', 'error': error_msg}
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)[:100]}"
            logger.error(f"❌ {error_msg}")
            return {'status': 'failed', 'error': error_msg}
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:100]}"
            logger.error(f"❌ {error_msg}")
            return {'status': 'failed', 'error': error_msg}

    def generate_all_test_signals(self) -> List[Dict[str, Any]]:
        """
        Generate ALL test signals upfront (40+ signals across 16 patterns)

        Returns:
            List of signal dicts with metadata
        """
        signals = []

        # =====================================================================
        # EQUITY PATTERNS (4 patterns)
        # =====================================================================

        # Pattern 1: SPY - Simple Entry → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P1_EQUITY_SPY',
                    'instrument': 'SPY',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 575.25,
                    'quantity': 50,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P1_EQUITY',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P1_EQUITY_SPY',
                    'instrument': 'SPY',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 576.80,
                    'quantity': 50,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P1_EQUITY',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 2: AAPL - Scale In (3 entries) → Full Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P2_EQUITY_AAPL',
                    'instrument': 'AAPL',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 230.50,
                    'quantity': 100,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P2_EQUITY',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P2_EQUITY_AAPL',
                    'instrument': 'AAPL',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 229.75,
                    'quantity': 50,
                    'signal_type': 'SCALE_IN',
                    'account': self.account
                },
                'pattern_id': 'P2_EQUITY',
                'sequence': 2,
                'type': 'SCALE_IN',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P2_EQUITY_AAPL',
                    'instrument': 'AAPL',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 229.00,
                    'quantity': 25,
                    'signal_type': 'SCALE_IN',
                    'account': self.account
                },
                'pattern_id': 'P2_EQUITY',
                'sequence': 3,
                'type': 'SCALE_IN',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P2_EQUITY_AAPL',
                    'instrument': 'AAPL',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 232.00,
                    'quantity': 175,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P2_EQUITY',
                'sequence': 4,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 3: TLT - Swing LONG → SHORT → LONG
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P3_EQUITY_TLT',
                    'instrument': 'TLT',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 95.50,
                    'quantity': 40,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P3_EQUITY',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P3_EQUITY_TLT',
                    'instrument': 'TLT',
                    'instrument_type': 'STOCK',
                    'direction': 'SHORT',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 94.80,
                    'quantity': 50,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P3_EQUITY',
                'sequence': 2,
                'type': 'FLIP_SHORT',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P3_EQUITY_TLT',
                    'instrument': 'TLT',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 95.20,
                    'quantity': 30,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P3_EQUITY',
                'sequence': 3,
                'type': 'FLIP_LONG',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P3_EQUITY_TLT',
                    'instrument': 'TLT',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 96.00,
                    'quantity': 20,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P3_EQUITY',
                'sequence': 4,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 4: TSLA - Partial Exits
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P4_EQUITY_TSLA',
                    'instrument': 'TSLA',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 425.00,
                    'quantity': 100,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P4_EQUITY',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P4_EQUITY_TSLA',
                    'instrument': 'TSLA',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 430.00,
                    'quantity': 30,
                    'signal_type': 'SCALE_OUT',
                    'account': self.account
                },
                'pattern_id': 'P4_EQUITY',
                'sequence': 2,
                'type': 'SCALE_OUT',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P4_EQUITY_TSLA',
                    'instrument': 'TSLA',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 435.00,
                    'quantity': 40,
                    'signal_type': 'SCALE_OUT',
                    'account': self.account
                },
                'pattern_id': 'P4_EQUITY',
                'sequence': 3,
                'type': 'SCALE_OUT',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P4_EQUITY_TSLA',
                    'instrument': 'TSLA',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 440.00,
                    'quantity': 30,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P4_EQUITY',
                'sequence': 4,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # SINGLE-LEG OPTIONS PATTERNS (4 patterns)
        # =====================================================================

        # Pattern 5: SPY Call - Entry → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P5_OPTION_SPY_CALL',
                    'instrument_type': 'OPTION',
                    'underlying': 'SPY',
                    'legs': [
                        {
                            'strike': 575.0,
                            'expiry': '20251128',
                            'right': 'C',
                            'action': 'BUY',
                            'quantity': 10
                        }
                    ],
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 5.50,
                    'quantity': 10,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P5_OPTION_SINGLE',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P5_OPTION_SPY_CALL',
                    'instrument_type': 'OPTION',
                    'underlying': 'SPY',
                    'legs': [
                        {
                            'strike': 575.0,
                            'expiry': '20251128',
                            'right': 'C',
                            'action': 'SELL',
                            'quantity': 10
                        }
                    ],
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 6.25,
                    'quantity': 10,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P5_OPTION_SINGLE',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 6: QQQ Put - Scale In → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P6_OPTION_QQQ_PUT',
                    'instrument_type': 'OPTION',
                    'underlying': 'QQQ',
                    'legs': [
                        {
                            'strike': 480.0,
                            'expiry': '20251128',
                            'right': 'P',
                            'action': 'BUY',
                            'quantity': 20
                        }
                    ],
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 4.75,
                    'quantity': 20,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P6_OPTION_SINGLE',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P6_OPTION_QQQ_PUT',
                    'instrument_type': 'OPTION',
                    'underlying': 'QQQ',
                    'legs': [
                        {
                            'strike': 480.0,
                            'expiry': '20251128',
                            'right': 'P',
                            'action': 'BUY',
                            'quantity': 10
                        }
                    ],
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 5.00,
                    'quantity': 10,
                    'signal_type': 'SCALE_IN',
                    'account': self.account
                },
                'pattern_id': 'P6_OPTION_SINGLE',
                'sequence': 2,
                'type': 'SCALE_IN',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P6_OPTION_QQQ_PUT',
                    'instrument_type': 'OPTION',
                    'underlying': 'QQQ',
                    'legs': [
                        {
                            'strike': 480.0,
                            'expiry': '20251128',
                            'right': 'P',
                            'action': 'SELL',
                            'quantity': 30
                        }
                    ],
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 5.50,
                    'quantity': 30,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P6_OPTION_SINGLE',
                'sequence': 3,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # MULTI-LEG OPTIONS PATTERNS (4 patterns)
        # =====================================================================

        # Pattern 9: SPY Iron Condor (4 legs)
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P9_OPTION_IRON_CONDOR',
                    'instrument_type': 'OPTION',
                    'underlying': 'SPY',
                    'legs': [
                        {'strike': 570.0, 'expiry': '20251128', 'right': 'P', 'action': 'BUY', 'quantity': 1},
                        {'strike': 575.0, 'expiry': '20251128', 'right': 'P', 'action': 'SELL', 'quantity': 1},
                        {'strike': 585.0, 'expiry': '20251128', 'right': 'C', 'action': 'SELL', 'quantity': 1},
                        {'strike': 590.0, 'expiry': '20251128', 'right': 'C', 'action': 'BUY', 'quantity': 1}
                    ],
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 1.50,
                    'quantity': 1,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P9_OPTION_MULTI',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P9_OPTION_IRON_CONDOR',
                    'instrument_type': 'OPTION',
                    'underlying': 'SPY',
                    'legs': [
                        {'strike': 570.0, 'expiry': '20251128', 'right': 'P', 'action': 'SELL', 'quantity': 1},
                        {'strike': 575.0, 'expiry': '20251128', 'right': 'P', 'action': 'BUY', 'quantity': 1},
                        {'strike': 585.0, 'expiry': '20251128', 'right': 'C', 'action': 'BUY', 'quantity': 1},
                        {'strike': 590.0, 'expiry': '20251128', 'right': 'C', 'action': 'SELL', 'quantity': 1}
                    ],
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 1.25,
                    'quantity': 1,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P9_OPTION_MULTI',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 10: SPY Bull Call Spread (2 legs)
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P10_OPTION_BULL_CALL_SPREAD',
                    'instrument_type': 'OPTION',
                    'underlying': 'SPY',
                    'legs': [
                        {'strike': 575.0, 'expiry': '20251128', 'right': 'C', 'action': 'BUY', 'quantity': 5},
                        {'strike': 585.0, 'expiry': '20251128', 'right': 'C', 'action': 'SELL', 'quantity': 5}
                    ],
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 3.50,
                    'quantity': 5,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P10_OPTION_MULTI',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P10_OPTION_BULL_CALL_SPREAD',
                    'instrument_type': 'OPTION',
                    'underlying': 'SPY',
                    'legs': [
                        {'strike': 575.0, 'expiry': '20251128', 'right': 'C', 'action': 'SELL', 'quantity': 5},
                        {'strike': 585.0, 'expiry': '20251128', 'right': 'C', 'action': 'BUY', 'quantity': 5}
                    ],
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 4.25,
                    'quantity': 5,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P10_OPTION_MULTI',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # FOREX PATTERNS (2 patterns)
        # =====================================================================

        # Pattern 13: EURUSD - Entry → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P13_FOREX_EURUSD',
                    'instrument': 'EURUSD',
                    'instrument_type': 'FOREX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 1.0850,
                    'quantity': 100000,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P13_FOREX',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P13_FOREX_EURUSD',
                    'instrument': 'EURUSD',
                    'instrument_type': 'FOREX',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 1.0900,
                    'quantity': 100000,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P13_FOREX',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 14: GBPUSD - Scale In → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P14_FOREX_GBPUSD',
                    'instrument': 'GBPUSD',
                    'instrument_type': 'FOREX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 1.2650,
                    'quantity': 100000,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P14_FOREX',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P14_FOREX_GBPUSD',
                    'instrument': 'GBPUSD',
                    'instrument_type': 'FOREX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 1.2640,
                    'quantity': 50000,
                    'signal_type': 'SCALE_IN',
                    'account': self.account
                },
                'pattern_id': 'P14_FOREX',
                'sequence': 2,
                'type': 'SCALE_IN',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P14_FOREX_GBPUSD',
                    'instrument': 'GBPUSD',
                    'instrument_type': 'FOREX',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 1.2700,
                    'quantity': 150000,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P14_FOREX',
                'sequence': 3,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # FUTURES PATTERNS (2 patterns)
        # =====================================================================

        # Pattern 15: GC (Gold) - Entry → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P15_FUTURE_GC',
                    'instrument': 'GC',
                    'instrument_type': 'FUTURE',
                    'expiry': '20251226',
                    'exchange': 'COMEX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 2650.00,
                    'quantity': 2,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P15_FUTURE',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P15_FUTURE_GC',
                    'instrument': 'GC',
                    'instrument_type': 'FUTURE',
                    'expiry': '20251226',
                    'exchange': 'COMEX',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 2675.00,
                    'quantity': 2,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P15_FUTURE',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 16: CL (Crude Oil) - Scale In → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'P16_FUTURE_CL',
                    'instrument': 'CL',
                    'instrument_type': 'FUTURE',
                    'expiry': '20251219',
                    'exchange': 'NYMEX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 75.50,
                    'quantity': 3,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P16_FUTURE',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P16_FUTURE_CL',
                    'instrument': 'CL',
                    'instrument_type': 'FUTURE',
                    'expiry': '20251219',
                    'exchange': 'NYMEX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 74.75,
                    'quantity': 2,
                    'signal_type': 'SCALE_IN',
                    'account': self.account
                },
                'pattern_id': 'P16_FUTURE',
                'sequence': 2,
                'type': 'SCALE_IN',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'P16_FUTURE_CL',
                    'instrument': 'CL',
                    'instrument_type': 'FUTURE',
                    'expiry': '20251219',
                    'exchange': 'NYMEX',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 77.00,
                    'quantity': 5,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P16_FUTURE',
                'sequence': 3,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        logger.info(f"📋 Generated {len(signals)} test signals across {len(set(s['pattern_id'] for s in signals))} patterns")
        return signals

    def smart_shuffle(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Shuffle signals while preserving entry→exit order per pattern

        Algorithm:
        1. Group signals by pattern_id
        2. Sort each group by sequence (preserve order within pattern)
        3. Shuffle the pattern groups themselves
        4. Flatten back to list

        Args:
            signals: List of signal dicts with pattern_id and sequence

        Returns:
            Shuffled list with preserved per-pattern ordering
        """
        # Group by pattern_id
        groups = defaultdict(list)
        for sig in signals:
            groups[sig['pattern_id']].append(sig)

        # Sort each group by sequence (preserve order)
        for pattern_id in groups:
            groups[pattern_id].sort(key=lambda x: x['sequence'])

        # Shuffle the groups themselves
        group_list = list(groups.values())
        random.shuffle(group_list)

        # Flatten back to list
        shuffled = []
        for group in group_list:
            shuffled.extend(group)

        logger.info(f"🎲 Shuffled {len(set(s['pattern_id'] for s in signals))} pattern groups")
        return shuffled

    def run_all_tests(self, shuffle: bool = True):
        """
        Main test orchestrator - generates, shuffles, sends, and reports

        Args:
            shuffle: Whether to shuffle pattern order (default: True)
        """
        logger.info("\n" + "="*100)
        logger.info("🚀 COMPREHENSIVE MULTI-ASSET SIGNAL TESTING")
        logger.info("="*100)
        logger.info(f"API URL: {self.api_url}")
        logger.info(f"Account: {self.account}")
        logger.info(f"Shuffle: {shuffle}")
        logger.info("\nThis will test:")
        logger.info("  - 4 Equity patterns (SPY, AAPL, TLT, TSLA)")
        logger.info("  - 2 Single-leg Options patterns (SPY Call, QQQ Put)")
        logger.info("  - 2 Multi-leg Options patterns (Iron Condor, Bull Call Spread)")
        logger.info("  - 2 Forex patterns (EURUSD, GBPUSD)")
        logger.info("  - 2 Futures patterns (GC Gold, CL Crude)")
        logger.info("\nPress Ctrl+C to cancel in 3 seconds...")
        time.sleep(3)

        # Generate all signals
        logger.info("\n🔄 Generating all test signals...")
        all_signals = self.generate_all_test_signals()

        # Shuffle if requested
        if shuffle:
            logger.info("\n🎲 Shuffling signal order (preserving entry→exit per pattern)...")
            all_signals = self.smart_shuffle(all_signals)
        else:
            logger.info("\n📋 Sending signals in sequential order (no shuffle)")

        # Print test plan
        logger.info("\n" + "="*100)
        logger.info("📊 TEST EXECUTION PLAN")
        logger.info("="*100)
        for i, sig in enumerate(all_signals, 1):
            inst = sig['signal'].get('instrument') or sig['signal'].get('underlying', 'N/A')
            inst_type = sig['signal'].get('instrument_type', 'N/A')
            logger.info(f"  {i:2d}. {sig['pattern_id']:25s} - {sig['type']:12s} | {inst_type:6s} | {inst}")

        # Execute test signals
        logger.info("\n" + "="*100)
        logger.info("🚀 STARTING TEST EXECUTION")
        logger.info("="*100)

        results = []
        for i, sig_item in enumerate(all_signals, 1):
            pattern = sig_item['pattern_id']
            sig_type = sig_item['type']
            signal_payload = sig_item['signal']

            inst = signal_payload.get('instrument') or signal_payload.get('underlying', 'N/A')
            inst_type = signal_payload.get('instrument_type', 'N/A')

            logger.info(f"\n[{i}/{len(all_signals)}] Sending {pattern} - {sig_type} ({inst_type}: {inst})...")

            result = self.send_signal(signal_payload)

            results.append({
                'pattern': pattern,
                'type': sig_type,
                'instrument_type': inst_type,
                'instrument': inst,
                'status': result['status'],
                'error': result.get('error', '')
            })

            # Wait before next signal
            time.sleep(sig_item.get('wait_after', 5))

        # Generate results table
        self.print_results_table(results)

    def print_results_table(self, results: List[Dict[str, Any]]):
        """
        Print summary table of test results

        Args:
            results: List of result dicts with status, pattern, instrument_type, etc.
        """
        try:
            from tabulate import tabulate
            has_tabulate = True
        except ImportError:
            has_tabulate = False
            logger.warning("⚠️  'tabulate' not installed - using simple table format")

        logger.info("\n" + "="*100)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("="*100)

        if has_tabulate:
            table_data = []
            for r in results:
                status_emoji = "✅" if r['status'] == 'success' else "❌"
                error_short = r['error'][:50] if r['error'] else ''
                table_data.append([
                    status_emoji,
                    r['pattern'],
                    r['instrument_type'],
                    r['instrument'],
                    r['type'],
                    error_short
                ])

            print(tabulate(table_data, headers=['Status', 'Pattern', 'Asset Type', 'Instrument', 'Signal Type', 'Error']))
        else:
            # Simple format without tabulate
            for r in results:
                status = "✅" if r['status'] == 'success' else "❌"
                error = f" | Error: {r['error'][:50]}" if r['error'] else ''
                print(f"{status} {r['pattern']:25s} | {r['instrument_type']:6s} | {r['instrument']:10s} | {r['type']:12s}{error}")

        # Summary stats
        total = len(results)
        success = sum(1 for r in results if r['status'] == 'success')
        failed = total - success

        logger.info(f"\n📈 Overall: {success}/{total} succeeded ({success/total*100:.1f}%)")
        logger.info(f"❌ Failed: {failed}/{total}")

        # Group by asset type
        by_asset = defaultdict(lambda: {'success': 0, 'failed': 0})
        for r in results:
            asset_type = r['instrument_type']
            if r['status'] == 'success':
                by_asset[asset_type]['success'] += 1
            else:
                by_asset[asset_type]['failed'] += 1

        logger.info("\n📊 Results by Asset Type:")
        for asset_type in sorted(by_asset.keys()):
            stats = by_asset[asset_type]
            total_asset = stats['success'] + stats['failed']
            pct = stats['success'] / total_asset * 100 if total_asset > 0 else 0
            logger.info(f"  {asset_type:10s}: {stats['success']}/{total_asset} ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description='Comprehensive Multi-Asset Signal Pattern Tester')
    parser.add_argument('--production', action='store_true', help='Use production endpoint (default: staging)')
    parser.add_argument('--no-shuffle', action='store_true', help='Disable shuffling (send in sequential order)')
    parser.add_argument('--asset-class', choices=['equity', 'options', 'forex', 'futures', 'all'],
                        default='all', help='Filter by asset class (default: all)')
    args = parser.parse_args()

    tester = ComprehensiveSignalTester(use_staging=not args.production)

    # TODO: Implement asset class filtering in future version
    if args.asset_class != 'all':
        logger.warning(f"⚠️  Asset class filtering not yet implemented - running all tests")

    tester.run_all_tests(shuffle=not args.no_shuffle)


if __name__ == '__main__':
    main()
