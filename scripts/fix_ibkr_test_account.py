#!/usr/bin/env python3
"""
Fix the IBKR_PAPER_TESTING account to match the working mock account structure.
Also update the fund's total_equity.
"""
from pymongo import MongoClient
from datetime import datetime

def fix_account():
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mathematricks_trading']
    
    account = db.trading_accounts.find_one({"account_id": "IBKR_PAPER_TESTING"})
    if not account:
        print("❌ IBKR_PAPER_TESTING account not found")
        return
    
    fund_id = account.get('fund_id')
    
    # Remove the problematic top-level fields that conflict with balances
    result = db.trading_accounts.update_one(
        {"account_id": "IBKR_PAPER_TESTING"},
        {
            "$unset": {
                "equity": "",
                "cash_balance": "",
                "margin_used": "",
                "margin_available": "",
                "unrealized_pnl": "",
                "realized_pnl": ""
            }
        }
    )
    
    print(f"✅ Removed top-level balance fields from IBKR_PAPER_TESTING (modified: {result.modified_count})")
    
    # Verify the fix
    account = db.trading_accounts.find_one({"account_id": "IBKR_PAPER_TESTING"})
    if account:
        print(f"\n📊 Account balances:")
        print(f"   Equity: ${account['balances']['equity']:,.2f}")
        print(f"   Cash: ${account['balances']['cash_balance']:,.2f}")
        print(f"   Buying Power: ${account['balances']['buying_power']:,.2f}")
        
        # Check if top-level equity field exists (it shouldn't)
        if 'equity' in account:
            print(f"\n⚠️  WARNING: Top-level equity field still exists: {account['equity']}")
        else:
            print(f"\n✅ Top-level balance fields removed successfully")
    
    # Update fund's total_equity
    if fund_id:
        print(f"\n📈 Updating fund {fund_id} total_equity...")
        
        # Get all accounts for this fund
        fund_accounts = list(db.trading_accounts.find({"fund_id": fund_id, "status": "ACTIVE"}))
        total_equity = sum(acc['balances']['equity'] for acc in fund_accounts)
        
        # Update fund
        db.funds.update_one(
            {"fund_id": fund_id},
            {
                "$set": {
                    "total_equity": total_equity,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        print(f"✅ Updated fund {fund_id} total_equity: ${total_equity:,.2f}")
        
        # Show all accounts in fund
        print(f"\n📋 Accounts in fund {fund_id}:")
        for acc in fund_accounts:
            print(f"   - {acc['account_id']}: ${acc['balances']['equity']:,.2f}")

if __name__ == '__main__':
    fix_account()
