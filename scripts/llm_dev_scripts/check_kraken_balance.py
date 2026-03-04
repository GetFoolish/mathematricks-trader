#!/usr/bin/env python3
"""
Check Kraken Account Balance
Connects to Kraken API and displays current account balances
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path (scripts/llm_dev_scripts -> scripts -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from project root
env_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=env_path)

from services.brokers.kraken.kraken_broker import KrakenBroker


def check_balance():
    """Check Kraken account balance"""
    
    # Get Kraken API credentials from environment
    api_key = os.getenv('KRAKEN_CANADA_API_KEY')
    api_secret = os.getenv('KRAKEN_CANADA_PRIVATE_KEY')
    
    if not api_key or not api_secret:
        print("❌ Error: KRAKEN_CANADA_API_KEY and KRAKEN_CANADA_PRIVATE_KEY must be set in .env")
        return False
    
    try:
        # Create Kraken broker instance
        config = {
            'api_key': api_key,
            'api_secret': api_secret,
            'testnet': True
        }
        
        print("🔌 Connecting to Kraken...")
        broker = KrakenBroker(config)
        
        # Connect to broker
        if not broker.connect():
            print("❌ Failed to connect to Kraken")
            return False
        
        print("✅ Connected successfully!\n")
        
        # Get account balance
        print("💰 Fetching account balance...")
        balance = broker.get_account_balance()
        
        print("\n" + "="*60)
        print("KRAKEN_CANADA Account Balance")
        print("="*60)
        print(f"Base Currency:     {balance.get('base_currency', 'USD')}")
        print(f"Total Equity:      ${balance.get('equity', 0):,.2f}")
        print(f"Cash Balance:      ${balance.get('cash_balance', 0):,.2f}")
        print(f"Margin Available:  ${balance.get('margin_available', 0):,.2f}")
        print(f"Margin Used:       ${balance.get('margin_used', 0):,.2f}")
        print(f"Unrealized P&L:    ${balance.get('unrealized_pnl', 0):,.2f}")
        print(f"Realized P&L:      ${balance.get('realized_pnl', 0):,.2f}")
        print("="*60)
        
        # Show crypto holdings if any
        if 'holdings' in balance and balance['holdings']:
            print("\n📊 Crypto Holdings:")
            print("-"*60)
            for symbol, amount in balance['holdings'].items():
                print(f"  {symbol:10s} {amount:,.8f}")
            print("-"*60)
        else:
            print("\n📊 No crypto holdings (USD only)")
        
        # Disconnect
        broker.disconnect()
        print("\n✅ Check complete!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking balance: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = check_balance()
    sys.exit(0 if success else 1)
