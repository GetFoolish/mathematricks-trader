"""
Database test helpers
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from pymongo.database import Database


class DatabaseTestHelper:
    """Helper class for database testing operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def seed_signals(self, signals: List[Dict]) -> List[str]:
        """Seed signals collection"""
        result = self.db.signals.insert_many(signals)
        return [str(id) for id in result.inserted_ids]
    
    def seed_strategies(self, strategies: List[Dict]) -> List[str]:
        """Seed strategies collection"""
        result = self.db.strategies.insert_many(strategies)
        return [str(id) for id in result.inserted_ids]
    
    def seed_accounts(self, accounts: List[Dict]) -> List[str]:
        """Seed accounts collection"""
        result = self.db.trading_accounts.insert_many(accounts)
        return [str(id) for id in result.inserted_ids]
    
    def seed_positions(self, positions: List[Dict]) -> List[str]:
        """Seed positions collection"""
        result = self.db.positions.insert_many(positions)
        return [str(id) for id in result.inserted_ids]
    
    def seed_orders(self, orders: List[Dict]) -> List[str]:
        """Seed orders collection"""
        result = self.db.orders.insert_many(orders)
        return [str(id) for id in result.inserted_ids]
    
    def clean_all_collections(self):
        """Clean all test collections"""
        collections = [
            "signals", "strategies", "trading_accounts",
            "positions", "orders", "executions"
        ]
        for collection in collections:
            self.db[collection].delete_many({})
    
    def get_signal_count(self, status: str = None) -> int:
        """Get count of signals by status"""
        filter_dict = {"status": status} if status else {}
        return self.db.signals.count_documents(filter_dict)
    
    def get_open_positions_count(self) -> int:
        """Get count of open positions"""
        return self.db.positions.count_documents({"status": "OPEN"})
    
    def get_filled_orders_count(self) -> int:
        """Get count of filled orders"""
        return self.db.orders.count_documents({"status": "FILLED"})
    
    def assert_signal_exists(self, signal_id: str):
        """Assert signal exists in database"""
        signal = self.db.signals.find_one({"signal_id": signal_id})
        assert signal is not None, f"Signal {signal_id} not found"
        return signal
    
    def assert_strategy_exists(self, strategy_id: str):
        """Assert strategy exists in database"""
        strategy = self.db.strategies.find_one({"strategy_id": strategy_id})
        assert strategy is not None, f"Strategy {strategy_id} not found"
        return strategy
    
    def assert_position_exists(self, position_id: str):
        """Assert position exists in database"""
        position = self.db.positions.find_one({"position_id": position_id})
        assert position is not None, f"Position {position_id} not found"
        return position
    
    def wait_for_signal_status(
        self,
        signal_id: str,
        expected_status: str,
        timeout: int = 10
    ):
        """Wait for signal to reach expected status"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            signal = self.db.signals.find_one({"signal_id": signal_id})
            if signal and signal.get("status") == expected_status:
                return signal
            time.sleep(0.5)
        
        raise TimeoutError(
            f"Signal {signal_id} did not reach status {expected_status} within {timeout}s"
        )


class MockDatabaseHelper:
    """Helper for mock database operations"""
    
    def __init__(self):
        self.collections = {
            "signals": [],
            "strategies": [],
            "positions": [],
            "orders": [],
            "trading_accounts": []
        }
    
    def insert(self, collection_name: str, document: Dict):
        """Insert document into mock collection"""
        if collection_name not in self.collections:
            self.collections[collection_name] = []
        self.collections[collection_name].append(document)
    
    def find_one(self, collection_name: str, filter_dict: Dict) -> Dict:
        """Find one document in mock collection"""
        if collection_name not in self.collections:
            return None
        
        for doc in self.collections[collection_name]:
            if all(doc.get(k) == v for k, v in filter_dict.items()):
                return doc
        return None
    
    def find(self, collection_name: str, filter_dict: Dict = None) -> List[Dict]:
        """Find documents in mock collection"""
        if collection_name not in self.collections:
            return []
        
        if filter_dict is None:
            return self.collections[collection_name].copy()
        
        results = []
        for doc in self.collections[collection_name]:
            if all(doc.get(k) == v for k, v in filter_dict.items()):
                results.append(doc)
        return results
    
    def clear(self):
        """Clear all mock collections"""
        for collection in self.collections.values():
            collection.clear()
