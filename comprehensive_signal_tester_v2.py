#!/usr/bin/env python3
"""
Comprehensive Multi-Asset Signal Testing Script v2

Uses REAL strategy names from MongoDB that have portfolio allocations.
Tracks IBKR order IDs and polls for final order status.

Real Strategies Available:
- SPY (Stock)
- TLT (Stock)
- Forex (Forex - EURUSD)
- SPX_0DE_Opt (Options)
- SPX_1-D_Opt (Options)
- Com1-Met (Futures - Gold GC)
- Com2-Ag (Futures - Silver SI)
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
from pymongo import MongoClient

# Load environment
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, '.env'))

# MongoDB connection with SSL configuration
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(mongo_uri, tlsAllowInvalidCertificates=True)
db = mongo_client['mathematricks_trading']

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveSignalTester:
    """Test signal patterns across multiple asset classes with REAL strategies"""

    def __init__(self, use_staging: bool = True, pause_play: bool = False):
        self.api_url = "https://staging.mathematricks.fund/api/signals" if use_staging else "https://mathematricks.fund/api/signals"
        self.account = "DU1234567"
        self.passphrase = "yahoo123"
        self.signal_to_order_map = {}  # Maps signal_id to order tracking info
        # If True, pause after each signal and wait for user to press Enter before continuing
        self.pause_play = bool(pause_play)

    def send_signal(self, signal_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a signal to the API

        Returns:
            Dict with 'status', 'signal_id', and optional 'error'
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

        signal_id = signal['signalID']

        try:
            response = requests.post(self.api_url, json=signal, timeout=10)

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
                return {'status': 'failed', 'signal_id': signal_id, 'error': error_msg}

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:100]}"
            logger.error(f"❌ {error_msg}")
            return {'status': 'failed', 'signal_id': signal_id, 'error': error_msg}

    def generate_all_test_signals(self) -> List[Dict[str, Any]]:
        """
        Generate test signals using REAL strategy names with allocations

        Returns:
            List of signal dicts with metadata
        """
        signals = []

        # =====================================================================
        # FOREX PATTERN - Real strategy: Forex (SENDING FIRST)
        # =====================================================================

        signals.extend([
            {
                'signal': {
                    'strategy_id': 'Forex',
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
                'pattern_id': 'P1_FOREX',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'Forex',
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
                'pattern_id': 'P1_FOREX',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # EQUITY PATTERNS - Real strategies: SPY, TLT
        # =====================================================================

        # Pattern 2: SPY - Simple Entry → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'SPY',
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
                'pattern_id': 'P1_SPY_STOCK',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'SPY',
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
                'pattern_id': 'P1_SPY_STOCK',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Pattern 2: TLT - Entry → Exit
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'TLT',
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
                'pattern_id': 'P2_TLT_STOCK',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'TLT',
                    'instrument': 'TLT',
                    'instrument_type': 'STOCK',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 96.00,
                    'quantity': 40,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P2_TLT_STOCK',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # FOREX PATTERN - Real strategy: Forex
        # =====================================================================

        signals.extend([
            {
                'signal': {
                    'strategy_id': 'Forex',
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
                'pattern_id': 'P3_FOREX',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'Forex',
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
                'pattern_id': 'P3_FOREX',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # OPTIONS PATTERNS - Real strategies: SPX_0DE_Opt, SPX_1-D_Opt
        # =====================================================================

        # Single-leg option (SPX_0DE_Opt)
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'SPX_0DE_Opt',
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
                'pattern_id': 'P4_SPX0DE_OPTION',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'SPX_0DE_Opt',
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
                'pattern_id': 'P4_SPX0DE_OPTION',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # Multi-leg option - Iron Condor (SPX_1-D_Opt)
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'SPX_1-D_Opt',
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
                'pattern_id': 'P5_SPX1D_IRON_CONDOR',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'SPX_1-D_Opt',
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
                'pattern_id': 'P5_SPX1D_IRON_CONDOR',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        # =====================================================================
        # FUTURES PATTERNS - Real strategies: Com1-Met (Gold), Com2-Ag (Silver)
        # =====================================================================

        # Gold futures (Com1-Met)
        signals.extend([
            {
                'signal': {
                    'strategy_id': 'Com1-Met',
                    'instrument': 'GC',
                    'instrument_type': 'FUTURE',
                    'expiry': '20250226',
                    'exchange': 'COMEX',
                    'direction': 'LONG',
                    'action': 'BUY',
                    'order_type': 'MARKET',
                    'price': 2650.00,
                    'quantity': 2,
                    'signal_type': 'ENTRY',
                    'account': self.account
                },
                'pattern_id': 'P6_COM1_GOLD',
                'sequence': 1,
                'type': 'ENTRY',
                'wait_after': 5
            },
            {
                'signal': {
                    'strategy_id': 'Com1-Met',
                    'instrument': 'GC',
                    'instrument_type': 'FUTURE',
                    'expiry': '20250226',
                    'exchange': 'COMEX',
                    'direction': 'LONG',
                    'action': 'SELL',
                    'order_type': 'MARKET',
                    'price': 2675.00,
                    'quantity': 2,
                    'signal_type': 'EXIT',
                    'account': self.account
                },
                'pattern_id': 'P6_COM1_GOLD',
                'sequence': 2,
                'type': 'EXIT',
                'wait_after': 5
            }
        ])

        logger.info(f"📋 Generated {len(signals)} test signals using REAL strategies with allocations")
        return signals

    def smart_shuffle(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Shuffle signals while preserving entry→exit order per pattern
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

    def poll_order_status(self, signal_id: str) -> Dict[str, Any]:
        """
        Poll MongoDB to get order status and IBKR order ID for a signal

        Returns:
            Dict with 'order_found', 'ibkr_order_id', 'cerebro_decision', 'order_status'
        """
        try:
            # Wait a bit for processing
            time.sleep(2)

            # Check standardized_signals for cerebro decision
            signal = db.standardized_signals.find_one({'signal_id': signal_id})

            # Check trading_orders collection
            order_id = f"{signal_id}_ORD"
            order = db.trading_orders.find_one({'order_id': order_id})

            if not order:
                return {
                    'order_found': False,
                    'cerebro_decision': 'REJECTED',
                    'ibkr_order_id': None,
                    'order_status': 'N/A'
                }

            # Order exists - check execution_confirmations for IBKR details
            confirmation = db.execution_confirmations.find_one({'order_id': order_id})

            if confirmation:
                return {
                    'order_found': True,
                    'cerebro_decision': 'APPROVED',
                    'ibkr_order_id': confirmation.get('ib_order_id', 'N/A'),
                    'order_status': confirmation.get('status', 'Unknown'),
                    'filled_qty': confirmation.get('filled_quantity', 0),
                    'fill_price': confirmation.get('average_fill_price', 0)
                }
            else:
                # Order created but no execution confirmation yet
                return {
                    'order_found': True,
                    'cerebro_decision': 'APPROVED',
                    'ibkr_order_id': 'Pending',
                    'order_status': order.get('status', 'PENDING'),
                    'filled_qty': 0,
                    'fill_price': 0
                }

        except Exception as e:
            logger.error(f"Error polling order status for {signal_id}: {e}")
            return {
                'order_found': False,
                'cerebro_decision': 'ERROR',
                'ibkr_order_id': None,
                'order_status': str(e)[:50]
            }

    def run_all_tests(self, shuffle: bool = True):
        """
        Main test orchestrator - generates, shuffles, sends, and reports
        """
        logger.info("\n" + "="*100)
        logger.info("🚀 COMPREHENSIVE MULTI-ASSET SIGNAL TESTING (Using REAL Strategies)")
        logger.info("="*100)
        logger.info(f"API URL: {self.api_url}")
        logger.info(f"Account: {self.account}")
        logger.info(f"Shuffle: {shuffle}")
        logger.info("\nUsing REAL strategies with allocations:")
        logger.info("  - SPY, TLT (Stocks)")
        logger.info("  - Forex (EURUSD)")
        logger.info("  - SPX_0DE_Opt, SPX_1-D_Opt (Options)")
        logger.info("  - Com1-Met, Com2-Ag (Futures)")
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
            strategy = sig['signal'].get('strategy_id')
            logger.info(f"  {i:2d}. {sig['pattern_id']:25s} - {sig['type']:12s} | {inst_type:6s} | {strategy:15s} | {inst}")

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
            strategy = signal_payload.get('strategy_id')

            logger.info(f"\n[{i}/{len(all_signals)}] Sending {pattern} - {sig_type} ({strategy}: {inst})...")

            result = self.send_signal(signal_payload)

            # Store signal_id for later polling
            if result['status'] == 'success':
                self.signal_to_order_map[result['signal_id']] = {
                    'pattern': pattern,
                    'type': sig_type,
                    'instrument_type': inst_type,
                    'instrument': inst,
                    'strategy': strategy
                }

            results.append({
                'pattern': pattern,
                'type': sig_type,
                'instrument_type': inst_type,
                'instrument': inst,
                'strategy': strategy,
                'signal_id': result.get('signal_id'),
                'status': result['status'],
                'error': result.get('error', '')
            })

            # Either pause for user input (interactive), or sleep for configured interval
            if self.pause_play:
                try:
                    input("Press Enter to continue to the next signal...")
                except Exception:
                    # If input isn't available (non-interactive environment), fall back to sleep
                    logger.info("Input not available; continuing without pause.")
                    time.sleep(sig_item.get('wait_after', 5))
            else:
                time.sleep(sig_item.get('wait_after', 5))

        # Poll for order statuses
        logger.info("\n" + "="*100)
        logger.info("🔍 POLLING ORDER STATUS FROM IBKR & CEREBRO...")
        logger.info("="*100)
        logger.info("Waiting 10 seconds for all orders to process...")
        time.sleep(10)

        for result in results:
            if result['status'] == 'success' and result['signal_id']:
                order_info = self.poll_order_status(result['signal_id'])
                result.update(order_info)
            else:
                result.update({
                    'order_found': False,
                    'cerebro_decision': 'N/A',
                    'ibkr_order_id': None,
                    'order_status': 'N/A'
                })

        # Generate results table
        self.print_results_table(results)

    def print_results_table(self, results: List[Dict[str, Any]]):
        """
        Print comprehensive results table with IBKR order tracking
        """
        try:
            from tabulate import tabulate
            has_tabulate = True
        except ImportError:
            has_tabulate = False
            logger.warning("⚠️  'tabulate' not installed - using simple table format")

        logger.info("\n" + "="*100)
        logger.info("📊 COMPREHENSIVE TEST RESULTS")
        logger.info("="*100)

        if has_tabulate:
            table_data = []
            for r in results:
                status_emoji = "✅" if r['status'] == 'success' else "❌"
                cerebro_emoji = "✅" if r.get('cerebro_decision') == 'APPROVED' else "❌"
                error_short = r['error'][:30] if r['error'] else ''

                table_data.append([
                    status_emoji,
                    r['strategy'][:15],
                    r['instrument_type'],
                    r['instrument'][:10],
                    r['type'][:10],
                    cerebro_emoji,
                    r.get('cerebro_decision', 'N/A')[:10],
                    r.get('ibkr_order_id', 'N/A'),
                    r.get('order_status', 'N/A')[:15],
                    error_short
                ])

            print(tabulate(table_data, headers=[
                'Sent',
                'Strategy',
                'Asset',
                'Instrument',
                'Type',
                'Cerebro',
                'Decision',
                'IBKR ID',
                'Fill Status',
                'Error'
            ]))
        else:
            # Simple format without tabulate
            for r in results:
                status = "✅" if r['status'] == 'success' else "❌"
                cerebro = "✅" if r.get('cerebro_decision') == 'APPROVED' else "❌"
                error = f" | Error: {r['error'][:30]}" if r['error'] else ''
                print(f"{status} {cerebro} {r['strategy']:15s} | {r['instrument_type']:6s} | {r['type']:10s} | IBKR ID: {r.get('ibkr_order_id', 'N/A')}{error}")

        # Summary stats
        total = len(results)
        sent_success = sum(1 for r in results if r['status'] == 'success')
        approved = sum(1 for r in results if r.get('cerebro_decision') == 'APPROVED')
        filled = sum(1 for r in results if r.get('filled_qty', 0) > 0)

        logger.info(f"\n📈 Summary:")
        logger.info(f"  Signals Sent Successfully: {sent_success}/{total} ({sent_success/total*100:.1f}%)")
        logger.info(f"  Approved by Cerebro: {approved}/{total} ({approved/total*100 if total > 0 else 0:.1f}%)")
        logger.info(f"  Filled by IBKR: {filled}/{total} ({filled/total*100 if total > 0 else 0:.1f}%)")

        # Group by asset type
        by_asset = defaultdict(lambda: {'sent': 0, 'approved': 0, 'filled': 0})
        for r in results:
            asset_type = r['instrument_type']
            if r['status'] == 'success':
                by_asset[asset_type]['sent'] += 1
            if r.get('cerebro_decision') == 'APPROVED':
                by_asset[asset_type]['approved'] += 1
            if r.get('filled_qty', 0) > 0:
                by_asset[asset_type]['filled'] += 1

        logger.info("\n📊 Results by Asset Type:")
        for asset_type in sorted(by_asset.keys()):
            stats = by_asset[asset_type]
            logger.info(f"  {asset_type:10s}: Sent: {stats['sent']}, Approved: {stats['approved']}, Filled: {stats['filled']}")


def main():
    parser = argparse.ArgumentParser(description='Comprehensive Multi-Asset Signal Pattern Tester v2')
    parser.add_argument('--production', action='store_true', help='Use production endpoint (default: staging)')
    parser.add_argument('--no-shuffle', action='store_true', help='Disable shuffling (send in sequential order)')
    parser.add_argument('--pause_play', '--pause-play', dest='pause_play', action='store_true', help='Pause after every signal and wait for Enter (interactive)')
    args = parser.parse_args()
    tester = ComprehensiveSignalTester(use_staging=not args.production, pause_play=args.pause_play)
    tester.run_all_tests(shuffle=not args.no_shuffle)


if __name__ == '__main__':
    main()
