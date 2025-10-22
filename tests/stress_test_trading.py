"""
Stress Test: Continuous Trading Simulation
==========================================

Simulates realistic trading activity by:
1. Randomly sending entry signals from active strategies
2. Tracking open positions
3. Sending exit signals after random hold periods
4. Handling Ctrl+C gracefully by closing all positions
5. Running continuously until interrupted

Usage:
    python tests/stress_test_trading.py [--interval SECONDS] [--max-positions N]

Example:
    python tests/stress_test_trading.py --interval 10 --max-positions 5
"""

import sys
import os
import time
import random
import signal
import json
import requests
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging
from ib_insync import IB, Stock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/stress_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CLOUD_ENDPOINT = "https://staging.mathematricks.fund/api/signals"
ACCOUNT_ID = "DU1234567"

# Active strategies with their instruments
ACTIVE_STRATEGIES = {
    'chong_vansh_strategy': {'instruments': ['SPY', 'QQQ', 'IWM'], 'allocation': 81.91},
    'SPX_1-D_Opt': {'instruments': ['SPY', 'SPX'], 'allocation': 57.79},
    'Com1-Met': {'instruments': ['GLD', 'SLV', 'GDX'], 'allocation': 43.09},
    'Com3-Mkt': {'instruments': ['DBA', 'DBB', 'DBC'], 'allocation': 17.07},
    'Forex': {'instruments': ['UUP', 'FXE', 'FXY'], 'allocation': 13.23},
    'Com2-Ag': {'instruments': ['DBA', 'CORN', 'WEAT'], 'allocation': 10.38},
    'SPY': {'instruments': ['SPY'], 'allocation': 6.54},
}

# Instrument price ranges (for realistic pricing)
INSTRUMENT_PRICES = {
    'SPY': (450, 470),
    'QQQ': (380, 400),
    'IWM': (200, 210),
    'SPX': (4500, 4700),
    'GLD': (180, 200),
    'SLV': (23, 25),
    'GDX': (30, 35),
    'DBA': (20, 22),
    'DBB': (18, 20),
    'DBC': (16, 18),
    'UUP': (27, 29),
    'FXE': (105, 110),
    'FXY': (67, 70),
    'CORN': (45, 50),
    'WEAT': (7, 9),
    'TLT': (90, 95),
}


@dataclass
class Position:
    """Represents an open position"""
    signal_id: str
    strategy: str
    instrument: str
    direction: str
    quantity: int
    entry_price: float
    entry_time: datetime
    
    def to_dict(self):
        d = asdict(self)
        d['entry_time'] = self.entry_time.isoformat()
        return d


class TradingStressTest:
    """Stress test manager"""
    
    def __init__(self, interval: int = 12, max_positions: int = 5):
        self.interval = interval
        self.max_positions = max_positions
        self.positions: Dict[str, Position] = {}
        self.signal_counter = 0
        self.running = True
        self.ib = None
        
        # Statistics
        self.total_entries = 0
        self.total_exits = 0
        self.total_signals_sent = 0
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        logger.info("\n" + "="*80)
        logger.info("🛑 SHUTDOWN SIGNAL RECEIVED - Closing all positions...")
        logger.info("="*80)
        self.running = False
    
    def connect_to_ibkr(self) -> bool:
        """Connect to IBKR for position cancellation"""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 7497, clientId=999)
            logger.info("✅ Connected to IBKR TWS for position management")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to IBKR: {e}")
            logger.warning("⚠️  Will not be able to cancel orders on shutdown")
            return False
    
    def cancel_all_orders_in_tws(self):
        """Cancel all pending orders in TWS"""
        if not self.ib or not self.ib.isConnected():
            logger.warning("⚠️  Not connected to IBKR - cannot cancel orders")
            return
        
        try:
            # Get all open orders
            open_orders = self.ib.openOrders()
            
            if not open_orders:
                logger.info("✅ No open orders in TWS to cancel")
                return
            
            logger.info(f"📋 Found {len(open_orders)} open orders in TWS")
            
            for trade in open_orders:
                try:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"   ❌ Cancelled order: {trade.order.orderId} - {trade.contract.symbol}")
                except Exception as e:
                    logger.error(f"   ⚠️  Failed to cancel order {trade.order.orderId}: {e}")
            
            # Wait for cancellations to process
            self.ib.sleep(2)
            
            # Verify all cancelled
            remaining = self.ib.openOrders()
            if remaining:
                logger.warning(f"⚠️  {len(remaining)} orders still open after cancellation")
            else:
                logger.info("✅ All orders successfully cancelled")
                
        except Exception as e:
            logger.error(f"❌ Error cancelling orders: {e}")
    
    def generate_signal_id(self, strategy: str, action: str) -> str:
        """Generate unique signal ID"""
        self.signal_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{strategy}_{timestamp}_{action}_{self.signal_counter:04d}"
    
    def get_random_price(self, instrument: str) -> float:
        """Get random realistic price for instrument"""
        if instrument in INSTRUMENT_PRICES:
            low, high = INSTRUMENT_PRICES[instrument]
            return round(random.uniform(low, high), 2)
        else:
            # Default price range for unknown instruments
            return round(random.uniform(50, 100), 2)
    
    def send_signal(self, signal_data: Dict) -> bool:
        """Send signal to cloud endpoint"""
        try:
            response = requests.post(
                CLOUD_ENDPOINT,
                json=signal_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                self.total_signals_sent += 1
                return True
            else:
                logger.error(f"❌ Signal rejected: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to send signal: {e}")
            return False
    
    def send_entry_signal(self) -> Optional[Position]:
        """Send a random entry signal"""
        # Pick random strategy
        strategy = random.choice(list(ACTIVE_STRATEGIES.keys()))
        strategy_info = ACTIVE_STRATEGIES[strategy]
        
        # Pick random instrument from strategy's instruments
        instrument = random.choice(strategy_info['instruments'])
        
        # Random direction
        direction = random.choice(['LONG', 'SHORT'])
        
        # Generate signal details
        signal_id = self.generate_signal_id(strategy, 'ENTRY')
        price = self.get_random_price(instrument)
        quantity = random.randint(10, 100)
        
        # Get timestamp
        now = datetime.utcnow()
        timestamp = now.isoformat() + "Z"
        epoch_time = int(now.timestamp())
        
        # Create signal payload matching cloud endpoint requirements
        signal_data = {
            # Required fields for cloud endpoint
            "strategy_name": strategy,
            "signal_sent_EPOCH": epoch_time,
            "signalID": signal_id,
            
            # Optional fields
            "passphrase": "yahoo123",
            "timestamp": timestamp,
            "account_id": ACCOUNT_ID,
            "signal": {
                "instrument": instrument,
                "direction": direction,
                "action": "ENTRY",
                "order_type": "MARKET",
                "quantity": quantity,
                "price": price,
                "stop_loss": price * 0.98 if direction == 'LONG' else price * 1.02,
                "take_profit": price * 1.05 if direction == 'LONG' else price * 0.95,
            },
            "metadata": {
                "source": "stress_test",
                "confidence": round(random.uniform(0.6, 0.95), 2),
                "strategy_allocation": strategy_info['allocation']
            }
        }
        
        logger.info("="*80)
        logger.info(f"📈 ENTRY SIGNAL: {strategy} | {instrument} | {direction}")
        logger.info(f"   Signal ID: {signal_id}")
        logger.info(f"   Quantity: {quantity} @ ${price}")
        logger.info("="*80)
        
        if self.send_signal(signal_data):
            # Track position
            position = Position(
                signal_id=signal_id,
                strategy=strategy,
                instrument=instrument,
                direction=direction,
                quantity=quantity,
                entry_price=price,
                entry_time=datetime.now()
            )
            self.positions[signal_id] = position
            self.total_entries += 1
            logger.info(f"✅ Entry signal sent - Now tracking {len(self.positions)} open positions")
            return position
        else:
            logger.error("❌ Failed to send entry signal")
            return None
    
    def send_exit_signal(self, position: Position):
        """Send exit signal for a position"""
        # Generate exit signal
        exit_signal_id = self.generate_signal_id(position.strategy, 'EXIT')
        current_price = self.get_random_price(position.instrument)
        
        # Calculate P&L
        if position.direction == 'LONG':
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        else:
            pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
        
        # Get timestamp
        now = datetime.utcnow()
        timestamp = now.isoformat() + "Z"
        epoch_time = int(now.timestamp())
        
        # Create exit signal payload matching cloud endpoint requirements
        signal_data = {
            # Required fields for cloud endpoint
            "strategy_name": position.strategy,
            "signal_sent_EPOCH": epoch_time,
            "signalID": exit_signal_id,
            
            # Optional fields
            "passphrase": "yahoo123",
            "timestamp": timestamp,
            "account_id": ACCOUNT_ID,
            "signal": {
                "instrument": position.instrument,
                "direction": position.direction,
                "action": "EXIT",
                "order_type": "MARKET",
                "quantity": position.quantity,
                "price": current_price,
            },
            "metadata": {
                "source": "stress_test",
                "entry_signal_id": position.signal_id,
                "entry_price": position.entry_price,
                "exit_price": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "hold_time_seconds": (datetime.now() - position.entry_time).total_seconds()
            }
        }
        
        pnl_emoji = "🟢" if pnl_pct > 0 else "🔴"
        logger.info("="*80)
        logger.info(f"📉 EXIT SIGNAL: {position.strategy} | {position.instrument}")
        logger.info(f"   Original Signal: {position.signal_id}")
        logger.info(f"   Exit Signal: {exit_signal_id}")
        logger.info(f"   Entry: ${position.entry_price} → Exit: ${current_price}")
        logger.info(f"   {pnl_emoji} P&L: {pnl_pct:+.2f}%")
        logger.info("="*80)
        
        if self.send_signal(signal_data):
            # Remove from tracked positions
            del self.positions[position.signal_id]
            self.total_exits += 1
            logger.info(f"✅ Exit signal sent - {len(self.positions)} positions remaining")
        else:
            logger.error("❌ Failed to send exit signal")
    
    def should_exit_position(self, position: Position) -> bool:
        """Determine if position should be exited"""
        # Random hold time between 30 seconds and 3 minutes
        hold_time = (datetime.now() - position.entry_time).total_seconds()
        min_hold = 30
        max_hold = 180
        
        if hold_time < min_hold:
            return False
        
        # Probability increases with time
        exit_probability = (hold_time - min_hold) / (max_hold - min_hold)
        return random.random() < exit_probability
    
    def run_cycle(self):
        """Run one cycle of the stress test"""
        # Decide action: entry or exit
        if len(self.positions) >= self.max_positions:
            # Must exit something
            action = 'exit'
        elif len(self.positions) == 0:
            # Must enter
            action = 'entry'
        else:
            # Random choice, but favor entries if we have capacity
            weights = [0.7, 0.3] if len(self.positions) < self.max_positions / 2 else [0.4, 0.6]
            action = random.choices(['entry', 'exit'], weights=weights)[0]
        
        if action == 'entry':
            self.send_entry_signal()
        else:
            # Check if any positions ready to exit
            eligible_positions = [p for p in self.positions.values() if self.should_exit_position(p)]
            
            if eligible_positions:
                # Exit random eligible position
                position = random.choice(eligible_positions)
                self.send_exit_signal(position)
            else:
                # No eligible positions, send entry instead
                logger.info("⏳ No positions ready to exit yet, sending entry instead")
                self.send_entry_signal()
    
    def print_status(self):
        """Print current status"""
        logger.info("\n" + "="*80)
        logger.info("📊 STRESS TEST STATUS")
        logger.info("="*80)
        logger.info(f"Total Signals Sent: {self.total_signals_sent}")
        logger.info(f"Total Entries: {self.total_entries}")
        logger.info(f"Total Exits: {self.total_exits}")
        logger.info(f"Open Positions: {len(self.positions)}")
        
        if self.positions:
            logger.info("\n📋 Current Open Positions:")
            for pos in self.positions.values():
                hold_time = (datetime.now() - pos.entry_time).total_seconds()
                logger.info(f"   • {pos.instrument} {pos.direction} x{pos.quantity} @ ${pos.entry_price} ({hold_time:.0f}s)")
        
        logger.info("="*80 + "\n")
    
    def cleanup(self):
        """Clean up on shutdown"""
        logger.info("\n" + "="*80)
        logger.info("🧹 CLEANUP PROCESS")
        logger.info("="*80)
        
        # Print final status
        self.print_status()
        
        # Send exit signals for all open positions
        if self.positions:
            logger.info(f"📤 Sending exit signals for {len(self.positions)} open positions...")
            positions_copy = list(self.positions.values())
            for position in positions_copy:
                self.send_exit_signal(position)
                time.sleep(1)  # Small delay between exits
        
        # Wait for signals to be processed
        logger.info("⏳ Waiting 5 seconds for signals to be processed...")
        time.sleep(5)
        
        # Cancel all orders in TWS
        logger.info("🛑 Cancelling all pending orders in TWS...")
        self.cancel_all_orders_in_tws()
        
        # Disconnect from IBKR
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("✅ Disconnected from IBKR")
        
        logger.info("\n" + "="*80)
        logger.info("✅ CLEANUP COMPLETE")
        logger.info("="*80)
        logger.info(f"Final Statistics:")
        logger.info(f"  • Total Signals Sent: {self.total_signals_sent}")
        logger.info(f"  • Total Entries: {self.total_entries}")
        logger.info(f"  • Total Exits: {self.total_exits}")
        logger.info("="*80 + "\n")
    
    def run(self):
        """Main run loop"""
        logger.info("\n" + "="*80)
        logger.info("🚀 TRADING STRESS TEST STARTED")
        logger.info("="*80)
        logger.info(f"Configuration:")
        logger.info(f"  • Interval: {self.interval} seconds")
        logger.info(f"  • Max Positions: {self.max_positions}")
        logger.info(f"  • Active Strategies: {len(ACTIVE_STRATEGIES)}")
        logger.info(f"  • Cloud Endpoint: {CLOUD_ENDPOINT}")
        logger.info(f"\n⚠️  Press Ctrl+C to stop and cleanup")
        logger.info("="*80 + "\n")
        
        # Connect to IBKR for cleanup capability
        self.connect_to_ibkr()
        
        # Initial delay
        time.sleep(2)
        
        cycle_count = 0
        
        try:
            while self.running:
                cycle_count += 1
                logger.info(f"\n🔄 Cycle {cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                self.run_cycle()
                
                # Print status every 5 cycles
                if cycle_count % 5 == 0:
                    self.print_status()
                
                # Wait for next cycle
                if self.running:
                    wait_time = random.randint(self.interval - 3, self.interval + 3)
                    logger.info(f"⏳ Waiting {wait_time} seconds until next cycle...\n")
                    time.sleep(wait_time)
                    
        except KeyboardInterrupt:
            # This shouldn't happen due to signal handler, but just in case
            logger.info("\n🛑 Keyboard interrupt received")
        finally:
            self.cleanup()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Trading Stress Test')
    parser.add_argument('--interval', type=int, default=12, help='Seconds between signals (default: 12)')
    parser.add_argument('--max-positions', type=int, default=5, help='Maximum open positions (default: 5)')
    
    args = parser.parse_args()
    
    # Validate
    if args.interval < 5:
        logger.error("❌ Interval must be at least 5 seconds")
        sys.exit(1)
    
    if args.max_positions < 1:
        logger.error("❌ Max positions must be at least 1")
        sys.exit(1)
    
    # Run test
    test = TradingStressTest(interval=args.interval, max_positions=args.max_positions)
    test.run()


if __name__ == "__main__":
    main()
