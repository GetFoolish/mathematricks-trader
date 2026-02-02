#!/usr/bin/env python3
"""
Update MongoDB trading_accounts with broker credentials
Moves credentials from .env into MongoDB authentication_details
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Connect to MongoDB
MONGODB_URI = os.getenv('MONGODB_URI_LOCAL', 'mongodb://localhost:27018/?directConnection=true')
client = MongoClient(MONGODB_URI)
db = client['mathematricks_trading']
trading_accounts = db['trading_accounts']

print("=" * 80)
print("UPDATING TRADING ACCOUNTS WITH BROKER CREDENTIALS")
print("=" * 80)

# Update IBKR-TESTING-ACCOUNT (Paper account)
result = trading_accounts.update_one(
    {"account_id": "IBKR-TESTING-ACCOUNT"},
    {"$set": {
        "authentication_details": {
            "username": "akasfz348",
            "password": "gagan114",
            "host": "ib-gateway-ibkr-testing-account",  # Will be created by gateway_controller
            "port": 4004,  # Paper port
            "client_id": 100,
            "trading_mode": "paper"
        }
    }}
)

if result.modified_count > 0:
    print("✅ Updated IBKR-TESTING-ACCOUNT with paper credentials")
else:
    print("⚠️  IBKR-TESTING-ACCOUNT not modified (already up to date or not found)")

print("\n" + "=" * 80)
print("EXAMPLE: Adding more accounts")
print("=" * 80)

print("""
# To add a new IBKR live account:
trading_accounts.insert_one({
    "account_id": "IBKR-LIVE-ACCOUNT-CANADA",
    "broker": "IBKR",
    "mode": "live",
    "status": "active",
    "fund_id": "main-fund",
    "authentication_details": {
        "username": "vandan0605",
        "password": "Gagan114#",
        "host": "ib-gateway-ibkr-live-account-canada",
        "port": 4003,  # Live port
        "client_id": 1,
        "trading_mode": "live"
    },
    "balances": {
        "base_currency": "USD",
        "equity": 100000.0,
        "cash_balance": 100000.0,
        "margin_used": 0.0,
        "margin_available": 100000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "margin_utilization_pct": 0.0
    },
    "open_positions": []
})

# To add a Binance account:
trading_accounts.insert_one({
    "account_id": "BINANCE-MAIN",
    "broker": "Binance",
    "mode": "live",
    "status": "active",
    "fund_id": "crypto-fund",
    "authentication_details": {
        "api_key": "your_binance_api_key",
        "api_secret": "your_binance_secret",
        "testnet": False
    },
    "balances": {
        "base_currency": "USDT",
        "equity": 10000.0,
        "cash_balance": 10000.0,
        "margin_used": 0.0,
        "margin_available": 10000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "margin_utilization_pct": 0.0
    },
    "open_positions": []
})

# To add a Bybit account:
trading_accounts.insert_one({
    "account_id": "BYBIT-FUTURES",
    "broker": "Bybit",
    "mode": "live",
    "status": "active",
    "fund_id": "crypto-fund",
    "authentication_details": {
        "api_key": "your_bybit_api_key",
        "api_secret": "your_bybit_secret",
        "testnet": False
    },
    "balances": {
        "base_currency": "USDT",
        "equity": 5000.0,
        "cash_balance": 5000.0,
        "margin_used": 0.0,
        "margin_available": 5000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "margin_utilization_pct": 0.0
    },
    "open_positions": []
})

# To add an Alpaca account:
trading_accounts.insert_one({
    "account_id": "ALPACA-PAPER",
    "broker": "Alpaca",
    "mode": "paper_mock",
    "status": "active",
    "fund_id": "test-fund",
    "authentication_details": {
        "api_key": "your_alpaca_key",
        "api_secret": "your_alpaca_secret",
        "paper": True
    },
    "balances": {
        "base_currency": "USD",
        "equity": 100000.0,
        "cash_balance": 100000.0,
        "margin_used": 0.0,
        "margin_available": 100000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "margin_utilization_pct": 0.0
    },
    "open_positions": []
})

# To add an Oanda account:
trading_accounts.insert_one({
    "account_id": "OANDA-FOREX",
    "broker": "Oanda",
    "mode": "live",
    "status": "active",
    "fund_id": "forex-fund",
    "authentication_details": {
        "api_key": "your_oanda_token",
        "practice": False  # True for practice account
    },
    "balances": {
        "base_currency": "USD",
        "equity": 50000.0,
        "cash_balance": 50000.0,
        "margin_used": 0.0,
        "margin_available": 50000.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
        "margin_utilization_pct": 0.0
    },
    "open_positions": []
})
""")

print("\n" + "=" * 80)
print("✅ Done!")
print("=" * 80)
