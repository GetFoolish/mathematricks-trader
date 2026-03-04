#!/usr/bin/env python3
"""
Update IBKR-PAPER and COINBASE-PAPER accounts with encrypted authentication details
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
from services.utils.encryption import encrypt_dict

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI_LOCAL', 'mongodb://localhost:27018/?directConnection=true')

# Encryption key from .env
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'Rk0lldbJxSvzJ4LNfufdoiYgUDe4oKA1d1k1dGhuyc8=')

def main():
    print("=" * 80)
    print("Updating Paper Trading Account Authentication Details")
    print("=" * 80)
    
    client = MongoClient(MONGODB_URI)
    db = client['mathematricks_trading']
    
    # 1. IBKR-PAPER authentication details (from seed data)
    ibkr_auth = {
        "host": "ib-gateway-ibkr-testing-account",
        "port": 4004,
        "client_id": 100,
        "password": "gagan114",
        "trading_mode": "paper",
        "username": "akasfz348",
        "totp_secret": "OZL3N3T75NXHZGYARX65S3MHXYU4M7DJ",
        "market_data_type": 1
    }
    
    # 2. COINBASE-PAPER authentication details (from .env)
    coinbase_auth = {
        "api_key_name": "organizations/813c3cb1-35fa-41e4-9b96-f5a05925dea9/apiKeys/d8e15f6b-5ec7-4784-984b-18e476130d7c",
        "api_key": "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIGX8bKjPTc7Dss17lY2rMVVnZkNJWEdd6F749xqmU6iYoAoGCCqGSM49\nAwEHoUQDQgAE+v+yvbASmVEkBWPxuw3FPEHLcaDVCkiuRBrI3+sryLO8eCK2E8H3\nW880XdHp3+HOaTtP7dWr5hHkRXVr0xxlUw==\n-----END EC PRIVATE KEY-----\n"
    }
    
    # Encrypt authentication details
    print("\n[1] Encrypting IBKR-PAPER authentication...")
    ibkr_encrypted = encrypt_dict(
        ibkr_auth,
        ["password", "username", "totp_secret"]  # Encrypt sensitive fields only
    )
    print(f"✅ Encrypted sensitive fields for IBKR-PAPER")
    
    print("\n[2] Encrypting COINBASE-PAPER authentication...")
    coinbase_encrypted = encrypt_dict(
        coinbase_auth,
        ["api_key_name", "api_key"]  # Encrypt both fields
    )
    print(f"✅ Encrypted sensitive fields for COINBASE-PAPER")
    
    # Update MongoDB
    print("\n[3] Updating IBKR-PAPER in MongoDB...")
    result = db.trading_accounts.update_one(
        {"account_id": "IBKR-PAPER"},
        {"$set": {"authentication_details": ibkr_encrypted}}
    )
    print(f"✅ Updated IBKR-PAPER: matched={result.matched_count}, modified={result.modified_count}")
    
    print("\n[4] Updating COINBASE-PAPER in MongoDB...")
    result = db.trading_accounts.update_one(
        {"account_id": "COINBASE-PAPER"},
        {"$set": {"authentication_details": coinbase_encrypted}}
    )
    print(f"✅ Updated COINBASE-PAPER: matched={result.matched_count}, modified={result.modified_count}")
    
    # Verify
    print("\n[5] Verification...")
    ibkr_account = db.trading_accounts.find_one({"account_id": "IBKR-PAPER"})
    coinbase_account = db.trading_accounts.find_one({"account_id": "COINBASE-PAPER"})
    
    print(f"  IBKR-PAPER authentication_details keys: {list(ibkr_account['authentication_details'].keys())}")
    print(f"  COINBASE-PAPER authentication_details keys: {list(coinbase_account['authentication_details'].keys())}")
    
    print("\n✅ Authentication details updated successfully!")
    print("\nNOTE: All sensitive fields are encrypted using ENCRYPTION_KEY from .env")

if __name__ == '__main__':
    main()
