#!/usr/bin/env python3
"""
Fetch account details from IBKR and Zerodha brokers
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../services'))

from brokers import BrokerFactory
from dotenv import load_dotenv

load_dotenv()

def fetch_ibkr_account():
    """Fetch and print IBKR account details"""
    print("\n" + "="*60)
    print("IBKR Account Details")
    print("="*60)

    config = {
        "broker": "IBKR",
        "host": os.getenv('IBKR_HOST', '127.0.0.1'),
        "port": int(os.getenv('IBKR_PORT', '7497')),
        "client_id": 99,  # Use unique client_id to avoid conflicts with ExecutionService
        "account_id": "IBKR_Main"
    }

    try:
        broker = BrokerFactory.create_broker(config)
        print(f"Connecting to {config['host']}:{config['port']}...")
        broker.connect()

        # Get account balance
        balance = broker.get_account_balance()
        print(f"\n✅ IBKR Connected - Account: {balance['account_id']}")
        print(f"   Equity: ${balance['equity']:,.2f}")
        print(f"   Cash: ${balance['cash_balance']:,.2f}")
        print(f"   Margin Used: ${balance['margin_used']:,.2f}")
        print(f"   Margin Available: ${balance['margin_available']:,.2f}")

        # Get positions
        positions = broker.get_open_positions()
        print(f"\n   Open Positions: {len(positions)}")
        for pos in positions:
            symbol = pos.get('symbol') or pos.get('ticker', 'UNKNOWN')
            quantity = pos.get('quantity', 0)
            avg_price = pos.get('avg_price', 0)
            current_price = pos.get('current_price', 0)
            market_value = pos.get('market_value', 0)
            unrealized_pnl = pos.get('unrealized_pnl', 0)
            side = pos.get('side', 'LONG')
            pnl_sign = "+" if unrealized_pnl >= 0 else ""
            print(f"     - {symbol}: {quantity} shares {side}")
            print(f"       Entry: ${avg_price:.2f} | Current: ${current_price:.2f} | Current Value: ${market_value:,.2f} | P&L: {pnl_sign}${unrealized_pnl:.2f}")

        broker.disconnect()
        return True

    except Exception as e:
        print(f"❌ IBKR Error: {e}")
        return False

def fetch_zerodha_account():
    """Fetch and print Zerodha account details"""
    print("\n" + "="*60)
    print("Zerodha Account Details")
    print("="*60)

    config = {
        "broker": "Zerodha",
        "api_key": os.getenv('ZERODHA_API_KEY'),
        "api_secret": os.getenv('ZERODHA_API_SECRET'),
        "access_token": os.getenv('ZERODHA_ACCESS_TOKEN'),
        "account_id": "Zerodha_Main"
    }

    if not config['api_key']:
        print("❌ Zerodha API key not found in .env")
        print("   Add to .env:")
        print("   ZERODHA_API_KEY=your_api_key")
        print("   ZERODHA_API_SECRET=your_api_secret")
        print("   ZERODHA_ACCESS_TOKEN=your_access_token")
        print("\n   Note: Access token requires manual login flow")
        print("   See: https://kite.trade/docs/connect/v3/user/")
        return False

    if not config['access_token']:
        print("❌ Zerodha access token not found")
        print("   You need to generate access token via Zerodha login flow")
        print("   API Key found:", config['api_key'])
        return False
    
    try:
        broker = BrokerFactory.create_broker(config)
        print("Connecting to Zerodha...")
        broker.connect()

        # Get account balance
        balance = broker.get_account_balance()
        print(f"\n✅ Zerodha Connected - Account: {balance['account_id']}")
        print(f"   Equity: ${balance['equity']:,.2f}")
        print(f"   Cash: ${balance['cash_balance']:,.2f}")
        print(f"   Margin Used: ${balance['margin_used']:,.2f}")
        print(f"   Margin Available: ${balance['margin_available']:,.2f}")

        # Get positions
        positions = broker.get_open_positions()
        print(f"\n   Open Positions: {len(positions)}")
        for pos in positions:
            symbol = pos.get('symbol') or pos.get('ticker', 'UNKNOWN')
            quantity = pos.get('quantity', 0)
            avg_price = pos.get('avg_price', 0)
            current_price = pos.get('current_price', 0)
            market_value = pos.get('market_value', 0)
            unrealized_pnl = pos.get('unrealized_pnl', 0)
            side = pos.get('side', 'LONG')
            pnl_sign = "+" if unrealized_pnl >= 0 else ""
            print(f"     - {symbol}: {quantity} shares {side}")
            print(f"       Entry: ${avg_price:.2f} | Current: ${current_price:.2f} | Current Value: ${market_value:,.2f} | P&L: {pnl_sign}${unrealized_pnl:.2f}")

        broker.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Zerodha Error: {e}")
        return False

if __name__ == "__main__":
    print("\nFetching account details from all brokers...\n")
    
    ibkr_ok = fetch_ibkr_account()
    zerodha_ok = fetch_zerodha_account()
    
    print("\n" + "="*60)
    print("Summary:")
    print(f"  IBKR: {'✅ SUCCESS' if ibkr_ok else '❌ FAILED'}")
    print(f"  Zerodha: {'✅ SUCCESS' if zerodha_ok else '❌ FAILED'}")
    print("="*60 + "\n")
