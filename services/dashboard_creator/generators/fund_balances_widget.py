"""
Fund Balances Widget Generator
Generates widget data showing fund totals with account breakdowns
"""
import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_fund_balances_widget(mongo_client: MongoClient, fund_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate Fund Balances widget data

    Args:
        mongo_client: MongoDB client instance
        fund_id: Optional fund ID to filter by. If None, shows all active funds.

    Returns:
        Dictionary with widget data structure
    """
    try:
        db = mongo_client['mathematricks_trading']
        funds_collection = db['funds']
        accounts_collection = db['trading_accounts']
        widget_data_collection = db['widget_data']

        # Query funds
        fund_query = {"status": "ACTIVE"}
        if fund_id:
            fund_query["fund_id"] = fund_id

        funds = list(funds_collection.find(fund_query))

        if not funds:
            logger.warning(f"No active funds found for fund_id={fund_id}")
            return _store_empty_widget_data(widget_data_collection, fund_id)

        # Build widget data
        total_equity = 0.0
        funds_data = []

        for fund in funds:
            # READ total_equity from fund document (don't recalculate)
            # Execution Service is the single source of truth
            fund_doc = funds_collection.find_one({"fund_id": fund['fund_id']})
            fund_total = fund_doc.get('total_equity', 0.0) if fund_doc else 0.0

            # Still get account-level breakdown for display
            accounts_data = []

            fund_accounts = list(accounts_collection.find({
                "fund_id": fund['fund_id'],
                "status": "ACTIVE"
            }))

            for account in fund_accounts:
                # Get balances from nested 'balances' object
                balances = account.get('balances', {})
                account_equity = balances.get('equity', 0.0)

                accounts_data.append({
                    "account_id": account.get('account_id'),
                    "broker": account.get('broker', 'UNKNOWN'),
                    "equity": account_equity,
                    "cash": balances.get('cash_balance', 0.0),
                    "margin_used": balances.get('margin_used', 0.0),
                    "unrealized_pnl": balances.get('unrealized_pnl', 0.0)
                })

            # Use MongoDB fund total_equity (not sum of accounts)
            total_equity += fund_total

            funds_data.append({
                "fund_id": fund['fund_id'],
                "fund_name": fund.get('name', fund['fund_id']),
                "total_balance": fund_total,  # From MongoDB, not calculated
                "accounts": accounts_data
            })

        # Create widget data structure
        widget_data = {
            "total_equity": total_equity,
            "funds": funds_data
        }

        # Store in widget_data collection
        _store_widget_data(
            widget_data_collection,
            widget_type="FundBalances",
            fund_id=fund_id,
            filters={},
            data=widget_data
        )

        logger.info(f"✅ Generated FundBalances widget: {len(funds_data)} funds, total equity: ${total_equity:,.2f}")
        return widget_data

    except Exception as e:
        logger.error(f"Error generating FundBalances widget: {e}", exc_info=True)
        raise

def _store_widget_data(
    widget_data_collection,
    widget_type: str,
    fund_id: Optional[str],
    filters: Dict[str, Any],
    data: Dict[str, Any]
):
    """Store widget data in MongoDB with deduplication"""
    # Create hash of filters for deduplication
    filters_str = json.dumps(filters, sort_keys=True)
    filters_hash = hashlib.md5(filters_str.encode()).hexdigest()

    now = datetime.utcnow()

    document = {
        "widget_type": widget_type,
        "fund_id": fund_id,
        "filters": filters,
        "filters_hash": filters_hash,
        "data": data,
        "computed_at": now,
        "ttl": 300,  # 5 minutes
        "created_at": now,
        "updated_at": now
    }

    # Upsert based on unique index (widget_type, fund_id, filters_hash)
    widget_data_collection.update_one(
        {
            "widget_type": widget_type,
            "fund_id": fund_id,
            "filters_hash": filters_hash
        },
        {"$set": document},
        upsert=True
    )

def _store_empty_widget_data(widget_data_collection, fund_id: Optional[str]) -> Dict[str, Any]:
    """Store empty widget data when no funds found"""
    empty_data = {
        "total_equity": 0.0,
        "funds": []
    }

    _store_widget_data(
        widget_data_collection,
        widget_type="FundBalances",
        fund_id=fund_id,
        filters={},
        data=empty_data
    )

    return empty_data

if __name__ == "__main__":
    # Test the widget generator
    client = MongoClient("mongodb://localhost:27017/")
    result = generate_fund_balances_widget(client)
    print(json.dumps(result, indent=2, default=str))
