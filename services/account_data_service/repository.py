"""
MongoDB repository for trading_accounts collection
"""
from pymongo.collection import Collection
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TradingAccountRepository:
    """Repository for trading_accounts CRUD operations"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def get_account(self, account_id: str) -> Optional[Dict]:
        """Get single account by ID"""
        return self.collection.find_one({"_id": account_id})

    def list_accounts(self, broker: str = None, status: str = "ACTIVE") -> List[Dict]:
        """
        List accounts with optional filters

        Args:
            broker: Filter by broker (e.g., "IBKR", "Zerodha")
            status: Filter by status (default: "ACTIVE")

        Returns:
            List of account documents
        """
        query = {"status": status}
        if broker:
            query["broker"] = broker
        return list(self.collection.find(query))

    def create_account(self, account_doc: Dict) -> str:
        """
        Create new trading account

        Args:
            account_doc: Complete account document

        Returns:
            account_id of created account
        """
        result = self.collection.insert_one(account_doc)
        logger.info(f"Created account: {account_doc['_id']}")
        return str(result.inserted_id)

    def update_balances(self, account_id: str, balances: Dict):
        """
        Update account balances with timestamp

        Args:
            account_id: Account ID
            balances: Balances dict (without last_updated - will be added)
        """
        balances_with_timestamp = {
            **balances,
            "last_updated": datetime.utcnow()
        }

        self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "balances": balances_with_timestamp,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.debug(f"Updated balances for {account_id}")

    def update_broker_positions_snapshot(self, account_id: str, positions: List[Dict]):
        """
        Store broker's position snapshot for monitoring/comparison only.
        Does NOT update open_positions (ExecutionService owns that field).

        This method stores the latest positions reported by the broker in a separate
        field so we can compare broker state vs. execution state and detect discrepancies.

        Args:
            account_id: Account ID
            positions: List of position dicts from broker
        """
        self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "broker_positions_snapshot": positions,
                    "broker_positions_last_updated": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.debug(f"Updated broker snapshot: {len(positions)} positions for {account_id}")

    def update_connection_status(self, account_id: str, status: str, success: bool):
        """
        Update connection status and poll time

        Args:
            account_id: Account ID
            status: Connection status ("CONNECTED", "DISCONNECTED", "ERROR")
            success: Whether the last poll was successful
        """
        self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "connection_status": status,
                    "last_poll_time": datetime.utcnow(),
                    "last_poll_success": success,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.debug(f"Updated connection status for {account_id}: {status}")

    def delete_account(self, account_id: str):
        """
        Soft delete account (set status to INACTIVE)

        Args:
            account_id: Account ID
        """
        self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "status": "INACTIVE",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"Deleted (soft) account: {account_id}")
