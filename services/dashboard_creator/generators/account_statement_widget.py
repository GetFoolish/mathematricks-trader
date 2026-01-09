"""
Account Statement Widget Generator
Generates transaction history for accounts with opening balance and running balance tracking
"""
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pymongo import MongoClient
from .balance_utils import get_balance_as_of_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_account_statement_widget(
    mongo_client: MongoClient,
    fund_id: Optional[str] = None,
    account_filter: Optional[str] = None,
    date_range_days: int = 30,
    group_by: str = "date"
) -> Dict[str, Any]:
    """
    Generate Account Statement widget data

    Args:
        mongo_client: MongoDB client instance
        fund_id: Optional fund ID to filter by
        account_filter: Optional account ID to filter by
        date_range_days: Number of days to look back (default: 30)
        group_by: Grouping method - "date" or "account" (default: "date")

    Returns:
        Dictionary with transaction data and summary
    """
    try:
        db = mongo_client['mathematricks_trading']
        signal_store = db['signal_store']
        widget_data_collection = db['widget_data']

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=date_range_days)

        # Build query for all signals with filled orders
        # Include both ENTRY signals (with closed positions) and EXIT signals
        query = {
            "execution.orders.filled_at": {"$exists": True, "$ne": None},
            "execution.status": "FILLED"
        }

        if fund_id:
            query["execution.orders.fund_id"] = fund_id

        if account_filter:
            query["execution.orders.account_id"] = account_filter

        # Get signals with filled orders
        signals = list(signal_store.find(query))

        # Extract transactions from orders
        transactions = []
        for signal in signals:
            signal_id = signal.get('signal_id', 'UNKNOWN')
            strategy_id = signal.get('strategy_id', 'UNKNOWN')

            # Extract signal_type and symbol from raw data
            raw = signal.get('raw', {})
            signal_type = raw.get('signal_type', 'UNKNOWN')
            legs = raw.get('legs', [])
            symbol = legs[0].get('instrument', 'UNKNOWN') if legs else 'UNKNOWN'

            execution = signal.get('execution', {})
            orders = execution.get('orders', [])
            position = signal.get('position', {})

            for order in orders:
                filled_at = order.get('filled_at')
                if not filled_at:
                    continue

                # Parse filled_at timestamp
                if isinstance(filled_at, str):
                    try:
                        filled_timestamp = datetime.fromisoformat(filled_at.replace('Z', '+00:00'))
                    except:
                        continue
                elif isinstance(filled_at, datetime):
                    filled_timestamp = filled_at
                else:
                    continue

                # Filter by date range
                if filled_timestamp < start_date or filled_timestamp > end_date:
                    continue

                # Get order-specific details
                order_account_id = order.get('account_id', 'UNKNOWN')
                order_fund_id = order.get('fund_id', 'UNKNOWN')
                filled_qty = order.get('quantity_filled', 0)
                avg_fill_price = order.get('avg_fill_price', 0)
                commission = order.get('commission', 0)

                # Calculate debit/credit based on ENTRY/EXIT
                # ENTRY = money out (debit), EXIT = money in (credit)
                notional_value = filled_qty * avg_fill_price

                if signal_type == 'ENTRY':
                    debit = notional_value + commission
                    credit = 0.0
                    description = f"BUY {symbol} - Entry"
                elif signal_type == 'EXIT':
                    debit = commission  # Only commission is debit
                    credit = notional_value
                    description = f"SELL {symbol} - Exit"
                else:
                    debit = 0.0
                    credit = 0.0
                    description = f"{signal_type} {symbol}"

                # Get realized P&L from position if available (for EXIT signals)
                realized_pnl = 0.0
                if signal_type == 'EXIT' and position:
                    pnl_data = position.get('pnl', {})
                    if isinstance(pnl_data, dict):
                        realized_pnl = pnl_data.get('net', 0.0)
                    else:
                        realized_pnl = pnl_data if pnl_data else 0.0

                transactions.append({
                    "date": filled_timestamp.strftime('%Y-%m-%d'),
                    "timestamp": filled_timestamp.isoformat(),
                    "account_id": order_account_id,
                    "fund_id": order_fund_id,
                    "strategy_id": strategy_id,
                    "type": "TRADE",
                    "description": description,
                    "signal_id": signal_id,
                    "symbol": symbol,
                    "debit": debit,
                    "credit": credit,
                    "realized_pnl": realized_pnl,
                    "commission": commission
                })

        # Sort transactions by timestamp (oldest first for balance calculation)
        transactions.sort(key=lambda x: x['timestamp'])

        # Get opening balances and add opening balance rows
        if account_filter:
            # Single account filter - add one opening balance row
            opening_balance = get_balance_as_of_date(mongo_client, account_filter, start_date)
            logger.info(f"Opening balance for {account_filter} at {start_date}: ${opening_balance:,.2f}")

            transactions.insert(0, {
                "date": start_date.strftime('%Y-%m-%d'),
                "timestamp": start_date.isoformat(),
                "account_id": account_filter,
                "fund_id": fund_id if fund_id else 'UNKNOWN',
                "strategy_id": "",
                "type": "OPENING_BALANCE",
                "description": "Opening Balance",
                "signal_id": "",
                "symbol": "",
                "debit": 0,
                "credit": 0,
                "realized_pnl": 0,
                "commission": 0,
                "balance": opening_balance
            })
        else:
            # No account filter - add opening balance for each unique account
            unique_accounts = list(set(t['account_id'] for t in transactions))
            opening_balance_rows = []
            for acc_id in sorted(unique_accounts):
                opening_balance = get_balance_as_of_date(mongo_client, acc_id, start_date)
                logger.info(f"Opening balance for {acc_id} at {start_date}: ${opening_balance:,.2f}")

                opening_balance_rows.append({
                    "date": start_date.strftime('%Y-%m-%d'),
                    "timestamp": start_date.isoformat(),
                    "account_id": acc_id,
                    "fund_id": fund_id if fund_id else 'UNKNOWN',
                    "strategy_id": "",
                    "type": "OPENING_BALANCE",
                    "description": "Opening Balance",
                    "signal_id": "",
                    "symbol": "",
                    "debit": 0,
                    "credit": 0,
                    "realized_pnl": 0,
                    "commission": 0,
                    "balance": opening_balance
                })

            # Insert all opening balance rows at the beginning
            for row in reversed(opening_balance_rows):
                transactions.insert(0, row)

        # Calculate running balance per account
        # Group transactions by account and calculate running balance for each
        account_balances = {}

        # First, set initial balances from opening balance rows
        for transaction in transactions:
            if transaction['type'] == 'OPENING_BALANCE':
                account_balances[transaction['account_id']] = transaction['balance']

        # Now calculate running balance for each transaction
        for transaction in transactions:
            if transaction['type'] == 'OPENING_BALANCE':
                continue  # Skip opening balance rows, already have balance set

            acc_id = transaction['account_id']
            if acc_id not in account_balances:
                account_balances[acc_id] = 0.0

            # Update running balance for this account
            # Note: realized_pnl is already reflected in the credit/debit amounts, don't add it separately
            account_balances[acc_id] += transaction['credit'] - transaction['debit']
            transaction['balance'] = account_balances[acc_id]

        # Calculate summary
        total_debits = sum(t['debit'] for t in transactions if t['type'] != 'OPENING_BALANCE')
        total_credits = sum(t['credit'] for t in transactions if t['type'] != 'OPENING_BALANCE')
        net_pnl = sum(t['realized_pnl'] for t in transactions if t['type'] != 'OPENING_BALANCE')
        transaction_count = len([t for t in transactions if t['type'] != 'OPENING_BALANCE'])

        # Reverse to newest first for display
        transactions.reverse()

        # Create widget data structure
        widget_data = {
            "transactions": transactions,
            "summary": {
                "total_debits": total_debits,
                "total_credits": total_credits,
                "net_pnl": net_pnl,
                "transaction_count": transaction_count,
                "date_range_days": date_range_days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        }

        # Store in widget_data collection
        _store_widget_data(
            widget_data_collection,
            widget_type="AccountStatement",
            fund_id=fund_id,
            filters={
                "account_filter": account_filter,
                "date_range_days": date_range_days,
                "group_by": group_by
            },
            data=widget_data
        )

        logger.info(
            f"✅ Generated AccountStatement widget: {transaction_count} transactions, "
            f"Net P&L: ${net_pnl:,.2f}, Range: {date_range_days} days, Account: {account_filter or 'All'}"
        )
        return widget_data

    except Exception as e:
        logger.error(f"Error generating AccountStatement widget: {e}", exc_info=True)
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

if __name__ == "__main__":
    # Test the widget generator
    client = MongoClient("mongodb://localhost:27018/?replicaSet=rs0")
    result = generate_account_statement_widget(client, account_filter="IBKR-MOCK", date_range_days=30)
    print(json.dumps(result, indent=2, default=str))
