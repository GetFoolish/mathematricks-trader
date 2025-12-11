#!/usr/bin/env python3
"""
Live Signal Testing Script for Max Hybrid Portfolio Management

This script:
1. Sends trading signals every 10 seconds
2. Monitors how signals are processed by Cerebro Service
3. Shows all the math and decision-making logic
4. Follows max_hybrid portfolio management technique

Requirements:
- All services must be running (run_mvp_demo.sh)
- MongoDB must be accessible
- Account data must be available
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import random

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment
load_dotenv(os.path.join(project_root, '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(project_root, 'logs', 'live_signal_tester.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiveSignalTester:
    """
    Test harness for live signal processing with max_hybrid portfolio logic
    """
    
    def __init__(self, passphrase: str = "yahoo123", interval: int = 10, account: str = "DU1234567", use_staging: bool = True):
        """
        Initialize the tester
        
        Args:
            passphrase: API passphrase for signal submission
            interval: Seconds between signals
            account: IBKR account name
            use_staging: Use staging cloud endpoint (default: True)
        """
        self.passphrase = passphrase
        self.interval = interval
        self.account = account
        
        # Send signals to cloud endpoint (same as TradingView)
        self.api_url = "https://staging.mathematricks.fund/api/signals" if use_staging else "https://mathematricks.fund/api/signals"
        
        # Account data is from local service
        self.account_api_url = "http://localhost:8002/api/v1"  # Account data service
        
        # MongoDB connection
        mongo_uri = os.getenv('MONGODB_URI')
        self.mongo_client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
        self.db = self.mongo_client['mathematricks_trading']
        
        # Test strategies (must match MongoDB data)
        self.test_strategies = [
            'Com1-Met',
            'Com2-Ag', 
            'Com3-Mkt',
            'Com4-Misc',
            'Forex',
            'SPY',
            'TLT',
            'SPX_1-D_Opt'
        ]
        
        # Test instruments
        self.instruments = ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'SPY', 'QQQ', 'IWM', 'DIA']
        
        self.signal_count = 0
        
    def get_account_state(self) -> Dict[str, Any]:
        """Fetch current account state from Account Data Service"""
        try:
            response = requests.get(f"{self.account_api_url}/account/{self.account}/state", timeout=5)
            response.raise_for_status()
            return response.json().get('state', {})
        except Exception as e:
            logger.error(f"Failed to get account state: {e}")
            return {}
    
    def send_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Send a signal to the ingestion endpoint"""
        try:
            response = requests.post(self.api_url, json=signal_data, timeout=10)
            response.raise_for_status()
            logger.info(f"✅ Signal sent successfully: {signal_data['signalID']}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send signal: {e}")
            return False
    
    def generate_test_signal(self, strategy_id: str = None, instrument: str = None, 
                            direction: str = None, action: str = None, 
                            price: float = None, quantity: int = None) -> Dict[str, Any]:
        """Generate a test signal (allows overriding randomness for entry/exit pairs)"""
        self.signal_count += 1
        now = datetime.now(timezone.utc)
        
        # Use provided values or random
        if strategy_id is None:
            strategy_id = random.choice(self.test_strategies)
        if instrument is None:
            instrument = random.choice(self.instruments)
        if direction is None:
            direction = random.choice(['LONG', 'SHORT'])
        if action is None:
            action = random.choice(['BUY', 'SELL'])
        if price is None:
            price = round(random.uniform(100, 500), 2)
        if quantity is None:
            quantity = random.randint(1, 100)
        
        signal_id = f"{strategy_id}_{now.strftime('%Y%m%d_%H%M%S')}_{self.signal_count:03d}"
        
        signal = {
            "strategy_name": strategy_id,
            "signal_sent_EPOCH": int(now.timestamp()),
            "signalID": signal_id,
            "passphrase": self.passphrase,
            "timestamp": now.isoformat(),
            "signal": {
                "strategy_id": strategy_id,
                "instrument": instrument,
                "direction": direction,
                "action": action,
                "order_type": "MARKET",
                "price": price,
                "quantity": quantity,
                "account": self.account
            }
        }
        
        return signal
    
    def fetch_cerebro_decision(self, signal_id: str, max_wait: int = 15) -> Dict[str, Any]:
        """Poll MongoDB for Cerebro decision"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            # Try exact match first
            decision = self.db['cerebro_decisions'].find_one({"signal_id": signal_id})
            if decision:
                return decision
            # Try partial match (signal_id might be compound after ingestion)
            decision = self.db['cerebro_decisions'].find_one({"signal_id": {"$regex": signal_id}})
            if decision:
                return decision
            time.sleep(0.5)
        return None
    
    def fetch_execution_confirmation(self, order_id: str, max_wait: int = 10) -> Dict[str, Any]:
        """Poll MongoDB for execution confirmation"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            confirmation = self.db['execution_confirmations'].find_one({"order_id": order_id})
            if confirmation:
                return confirmation
            time.sleep(0.5)
        return None
    
    def fetch_execution_order(self, signal_id: str, max_wait: int = 5) -> Dict[str, Any]:
        """Poll MongoDB for execution order"""
        order_id = f"{signal_id}_ORD"
        start_time = time.time()
        while time.time() - start_time < max_wait:
            order = self.db['trading_orders'].find_one({"order_id": order_id})
            if order:
                return order
            time.sleep(0.5)
        return None
    
    def print_signal_analysis(self, signal: Dict[str, Any], account_state: Dict[str, Any], 
                             decision: Dict[str, Any], order: Dict[str, Any], execution: Dict[str, Any] = None):
        """
        Print comprehensive analysis of signal processing with all math
        """
        print("\n" + "="*100)
        print(f"🎯 SIGNAL ANALYSIS - {signal['signalID']}")
        print("="*100)
        
        # Signal details
        sig = signal['signal']
        print(f"\n📨 INCOMING SIGNAL:")
        print(f"   Strategy: {sig['strategy_id']}")
        print(f"   Instrument: {sig['instrument']}")
        print(f"   Direction: {sig['direction']}")
        print(f"   Action: {sig['action']}")
        print(f"   Price: ${sig['price']:,.2f}")
        print(f"   Requested Quantity: {sig['quantity']}")
        
        # Account state
        if account_state:
            print(f"\n💰 ACCOUNT STATE (Before Signal):")
            print(f"   Account: {self.account}")
            equity = account_state.get('equity', 0)
            cash = account_state.get('cash_balance', 0)
            margin_used = account_state.get('margin_used', 0)
            margin_avail = account_state.get('margin_available', 0)
            
            print(f"   Total Equity: ${equity:,.2f}")
            print(f"   Cash Balance: ${cash:,.2f}")
            print(f"   Margin Used: ${margin_used:,.2f}")
            print(f"   Margin Available: ${margin_avail:,.2f}")
            if equity > 0:
                margin_pct = (margin_used / equity) * 100
                print(f"   Margin Used %: {margin_pct:.2f}%")
        else:
            print(f"\n💰 ACCOUNT STATE: Not available")
        
        # Cerebro decision
        if decision:
            print(f"\n🧠 CEREBRO DECISION (Max Hybrid Portfolio Logic):")
            print(f"   Decision: {decision.get('decision', 'UNKNOWN')}")
            print(f"   Reason: {decision.get('reason', 'N/A')}")
            print(f"   Original Quantity: {decision.get('original_quantity', 0)}")
            print(f"   Final Quantity: {decision.get('final_quantity', 0)}")
            
            risk = decision.get('risk_assessment', {})
            if risk:
                print(f"\n📊 RISK ASSESSMENT & MATH:")
                if risk.get('allocated_capital'):
                    print(f"   Allocated Capital: ${risk['allocated_capital']:,.2f}")
                if risk.get('margin_required'):
                    print(f"   Margin Required: ${risk['margin_required']:,.2f}")
                
                metadata = risk.get('metadata', {})
                if metadata:
                    print(f"\n   🔢 Portfolio Construction Math:")
                    if 'allocation_pct' in metadata:
                        print(f"      Strategy Allocation: {metadata['allocation_pct']:.2f}%")
                    if 'portfolio_equity' in metadata:
                        print(f"      Portfolio Equity: ${metadata['portfolio_equity']:,.2f}")
                    if 'position_size_calculation' in metadata:
                        print(f"      Position Sizing: {metadata['position_size_calculation']}")
        else:
            print(f"\n🧠 CEREBRO DECISION: Not found (timeout or error)")
        
        # Execution order
        if order:
            print(f"\n📋 TRADING ORDER (Sent to Execution):")
            print(f"   Order ID: {order.get('order_id')}")
            print(f"   Instrument: {order.get('instrument')}")
            print(f"   Direction: {order.get('direction')}")
            print(f"   Order Type: {order.get('order_type')}")
            print(f"   Price: ${order.get('price', 0):,.2f}")
            print(f"   Quantity: {order.get('quantity', 0)} shares")
            print(f"   Status: {order.get('status', 'PENDING')}")
            
            if order.get('quantity', 0) > 0:
                notional = order.get('quantity', 0) * order.get('price', 0)
                print(f"   Notional Value: ${notional:,.2f}")
        else:
            print(f"\n📋 TRADING ORDER: Not created (signal rejected or error)")
        
        # Execution confirmation
        if execution:
            print(f"\n✅ EXECUTION CONFIRMATION (From IBKR):")
            print(f"   Execution ID: {execution.get('execution_id')}")
            print(f"   Status: {execution.get('status', 'UNKNOWN')}")
            print(f"   Filled Quantity: {execution.get('quantity', 0)}")
            print(f"   Avg Fill Price: ${execution.get('price', 0):,.2f}")
            print(f"   Commission: ${execution.get('commission', 0):,.2f}")
            if execution.get('quantity', 0) > 0 and execution.get('price', 0) > 0:
                total = execution.get('quantity', 0) * execution.get('price', 0)
                print(f"   Total Value: ${total:,.2f}")
        
        print("\n" + "="*100 + "\n")
    
    def run_continuous_test(self, num_signals: int = None):
        """
        Run continuous signal testing with ENTRY + EXIT pairs
        
        Args:
            num_signals: Number of ENTRY/EXIT pairs to send (None = infinite)
                        --count 2 means 2 pairs = 4 total signals (2 entry + 2 exit)
        """
        logger.info("🚀 Starting Live Signal Tester (ENTRY + EXIT Pairs)")
        logger.info(f"   Interval: {self.interval} seconds between pairs")
        logger.info(f"   Account: {self.account}")
        logger.info(f"   Max Pairs: {'Infinite' if num_signals is None else num_signals}")
        logger.info("="*100)
        
        pair_count = 0
        try:
            while num_signals is None or pair_count < num_signals:
                pair_count += 1
                
                # ==================== ENTRY SIGNAL ====================
                logger.info(f"\n{'='*100}")
                logger.info(f"📈 PAIR #{pair_count} - ENTRY SIGNAL")
                logger.info(f"{'='*100}\n")
                
                # Get current account state
                logger.info(f"📊 Fetching account state...")
                account_state = self.get_account_state()
                
                # Generate ENTRY signal (random strategy/instrument/direction)
                logger.info(f"🎯 Generating ENTRY signal...")
                strategy_id = random.choice(self.test_strategies)
                instrument = random.choice(self.instruments)
                direction = random.choice(['LONG', 'SHORT'])
                entry_action = 'BUY' if direction == 'LONG' else 'SELL'
                price = round(random.uniform(100, 500), 2)
                quantity = random.randint(10, 100)
                
                entry_signal = self.generate_test_signal(
                    strategy_id=strategy_id,
                    instrument=instrument, 
                    direction=direction,
                    action=entry_action,
                    price=price,
                    quantity=quantity
                )
                
                if self.send_signal(entry_signal):
                    signal_id = entry_signal['signalID']
                    
                    # Wait for processing
                    logger.info(f"⏳ Waiting for Cerebro decision...")
                    time.sleep(2)
                    
                    # Fetch decision, order, and execution
                    decision = self.fetch_cerebro_decision(signal_id)
                    order = self.fetch_execution_order(signal_id)
                    
                    # Wait for execution confirmation
                    execution = None
                    if order and order.get('status') != 'REJECTED':
                        order_id = order.get('order_id')
                        logger.info(f"⏳ Waiting for execution confirmation from IBKR...")
                        execution = self.fetch_execution_confirmation(order_id, max_wait=10)
                    
                    # Print analysis
                    self.print_signal_analysis(entry_signal, account_state, decision, order, execution)
                    
                    # If entry was rejected, skip the exit
                    if decision and decision.get('decision') == 'REJECT':
                        logger.info(f"⚠️  Entry signal rejected - skipping exit signal for this pair\n")
                        if num_signals is None or pair_count < num_signals:
                            logger.info(f"⏰ Waiting {self.interval} seconds before next pair...\n")
                            time.sleep(self.interval)
                        continue
                
                # ==================== EXIT SIGNAL ====================
                logger.info(f"\n{'='*100}")
                logger.info(f"📉 PAIR #{pair_count} - EXIT SIGNAL (20-30s after entry)")
                logger.info(f"{'='*100}\n")
                
                # Wait 20-30 seconds before sending exit
                exit_wait = random.randint(20, 30)
                logger.info(f"⏰ Waiting {exit_wait} seconds before sending exit signal...")
                time.sleep(exit_wait)
                
                # Get updated account state
                logger.info(f"📊 Fetching account state...")
                account_state = self.get_account_state()
                
                # Generate EXIT signal (opposite action, same instrument/direction)
                logger.info(f"🎯 Generating EXIT signal...")
                exit_action = 'SELL' if direction == 'LONG' else 'BUY'
                exit_price = price * random.uniform(0.98, 1.02)  # Simulate price movement
                
                exit_signal = self.generate_test_signal(
                    strategy_id=strategy_id,
                    instrument=instrument,
                    direction=direction,
                    action=exit_action,
                    price=exit_price,
                    quantity=quantity
                )
                
                if self.send_signal(exit_signal):
                    signal_id = exit_signal['signalID']
                    
                    # Wait for processing
                    logger.info(f"⏳ Waiting for Cerebro decision...")
                    time.sleep(2)
                    
                    # Fetch decision, order, and execution
                    decision = self.fetch_cerebro_decision(signal_id)
                    order = self.fetch_execution_order(signal_id)
                    
                    # Wait for execution confirmation
                    execution = None
                    if order and order.get('status') != 'REJECTED':
                        order_id = order.get('order_id')
                        logger.info(f"⏳ Waiting for execution confirmation from IBKR...")
                        execution = self.fetch_execution_confirmation(order_id, max_wait=10)
                    
                    # Print analysis
                    self.print_signal_analysis(exit_signal, account_state, decision, order, execution)
                
                # Wait before next pair
                if num_signals is None or pair_count < num_signals:
                    logger.info(f"\n⏰ Waiting {self.interval} seconds before next pair...\n")
                    time.sleep(self.interval)
        
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Interrupted by user")
        
        logger.info(f"\n✅ Test complete. Sent {pair_count} pairs ({pair_count * 2} signals total).")



def main():
    parser = argparse.ArgumentParser(description='Live Signal Tester for Max Hybrid Portfolio (Entry/Exit Pairs)')
    parser.add_argument('--interval', type=int, default=10, help='Seconds between PAIRS (default: 10)')
    parser.add_argument('--count', type=int, default=None, help='Number of ENTRY/EXIT pairs to send (e.g., --count 2 = 4 signals total)')
    parser.add_argument('--account', type=str, default='DU1234567', help='IBKR account name')
    parser.add_argument('--passphrase', type=str, default='yahoo123', help='API passphrase')
    parser.add_argument('--production', action='store_true', help='Use production endpoint instead of staging')
    
    args = parser.parse_args()
    
    tester = LiveSignalTester(
        passphrase=args.passphrase,
        interval=args.interval,
        account=args.account,
        use_staging=not args.production
    )
    
    tester.run_continuous_test(num_signals=args.count)


if __name__ == '__main__':
    main()
