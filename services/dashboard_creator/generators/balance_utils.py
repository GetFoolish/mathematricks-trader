"""
Balance History Utilities
Provides functions to query account balances at specific dates
"""
import logging
from datetime import datetime
from typing import Optional
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_balance_as_of_date(
    mongo_client: MongoClient,
    account_id: str,
    target_date: datetime
) -> float:
    """
    Get account balance as of a specific date by reconstructing from transaction ledger.

    Args:
        mongo_client: MongoDB client instance
        account_id: Account ID to query balance for
        target_date: Date to get balance at

    Returns:
        Account equity at target_date
    """
    try:
        db = mongo_client['mathematricks_trading']

        # Get account's initial equity and creation date
        account = db['trading_accounts'].find_one(
            {"account_id": account_id},
            {"balances.initial_equity": 1, "created_at": 1}
        )

        if not account:
            logger.warning(f"Account {account_id} not found")
            return 0.0

        initial_equity = account.get('balances', {}).get('initial_equity', 1000000.0)
        created_at = account.get('created_at')

        # If target_date is before or at creation, return initial equity
        if created_at and target_date <= created_at:
            logger.info(f"Target date {target_date} is at/before creation date, returning initial equity: {initial_equity}")
            return initial_equity

        # Reconstruct balance from transaction ledger
        balance = initial_equity
        logger.info(f"Starting balance reconstruction for {account_id} from initial equity: {initial_equity}")

        # Query all closed positions before target_date for this account
        signals = list(db['signal_store'].find({
            "position.status": "CLOSED",
            "position.closed_at": {"$lte": target_date},
            "execution.orders.account_id": account_id
        }))

        logger.info(f"Found {len(signals)} closed positions for {account_id} before {target_date}")

        # Process each signal's P&L
        for signal in signals:
            raw = signal.get('raw', {})
            signal_type = raw.get('signal_type', 'UNKNOWN')
            position = signal.get('position', {})

            # Only EXIT signals have realized P&L
            if signal_type == 'EXIT' and position:
                pnl_data = position.get('pnl', {})
                if isinstance(pnl_data, dict):
                    realized_pnl = pnl_data.get('net', 0.0)
                    balance += realized_pnl
                    logger.debug(f"Added P&L from signal {signal.get('signal_id')}: {realized_pnl}, new balance: {balance}")

        logger.info(f"Final reconstructed balance for {account_id} at {target_date}: {balance}")
        return balance

    except Exception as e:
        logger.error(f"Error getting balance as of date for {account_id}: {e}", exc_info=True)
        return 0.0
