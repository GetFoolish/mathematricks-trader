"""
Test fixtures for database-related tests
Provides MongoDB fixtures and test data
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import pytest
from pymongo import MongoClient


@pytest.fixture
def clean_signals_collection(signals_collection):
    """Clean signals collection before test"""
    signals_collection.delete_many({})
    yield signals_collection
    signals_collection.delete_many({})


@pytest.fixture
def clean_strategies_collection(strategies_collection):
    """Clean strategies collection before test"""
    strategies_collection.delete_many({})
    yield strategies_collection
    strategies_collection.delete_many({})


@pytest.fixture
def clean_positions_collection(positions_collection):
    """Clean positions collection before test"""
    positions_collection.delete_many({})
    yield positions_collection
    positions_collection.delete_many({})


@pytest.fixture
def clean_orders_collection(orders_collection):
    """Clean orders collection before test"""
    orders_collection.delete_many({})
    yield orders_collection
    orders_collection.delete_many({})


@pytest.fixture
def clean_accounts_collection(accounts_collection):
    """Clean accounts collection before test"""
    accounts_collection.delete_many({})
    yield accounts_collection
    accounts_collection.delete_many({})


@pytest.fixture
def sample_signals_batch() -> List[Dict[str, Any]]:
    """Create batch of sample signals"""
    signals = []
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]
    
    for i, symbol in enumerate(symbols):
        # ENTRY signal
        signals.append({
            "signal_id": f"sig_entry_{i}",
            "strategy_id": "test_strategy",
            "symbol": symbol,
            "action": "ENTRY",
            "signal_type": "LONG",
            "timestamp": (datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat(),
            "price": 150.00 + i,
            "stop_loss": 145.00 + i,
            "take_profit": 160.00 + i,
            "quantity": 100,
            "status": "PENDING",
            "metadata": {"confidence": 0.85}
        })
        
        # EXIT signal
        signals.append({
            "signal_id": f"sig_exit_{i}",
            "strategy_id": "test_strategy",
            "symbol": symbol,
            "action": "EXIT",
            "signal_type": "LONG",
            "timestamp": (datetime.now(timezone.utc) + timedelta(hours=1, seconds=i)).isoformat(),
            "price": 155.00 + i,
            "quantity": 100,
            "status": "PENDING",
            "metadata": {"reason": "take_profit"}
        })
    
    return signals


@pytest.fixture
def sample_strategies_batch() -> List[Dict[str, Any]]:
    """Create batch of sample strategies"""
    return [
        {
            "strategy_id": "strat_001",
            "strategy_name": "Momentum Strategy",
            "is_active": True,
            "trading_mode": "LIVE_PAPER",
            "symbols": ["AAPL", "GOOGL"],
            "max_position_size": 10000,
            "risk_per_trade": 0.02,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "strategy_id": "strat_002",
            "strategy_name": "Mean Reversion Strategy",
            "is_active": True,
            "trading_mode": "BACKTEST",
            "symbols": ["MSFT", "TSLA"],
            "max_position_size": 5000,
            "risk_per_trade": 0.01,
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "strategy_id": "strat_003",
            "strategy_name": "Inactive Strategy",
            "is_active": False,
            "trading_mode": "LIVE_PAPER",
            "symbols": ["SPY"],
            "max_position_size": 20000,
            "risk_per_trade": 0.03,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]


@pytest.fixture
def sample_positions_batch() -> List[Dict[str, Any]]:
    """Create batch of sample positions"""
    return [
        {
            "position_id": "pos_001",
            "strategy_id": "strat_001",
            "account_id": "acc_001",
            "signal_id": "sig_entry_0",
            "symbol": "AAPL",
            "position_type": "LONG",
            "quantity": 100,
            "entry_price": 150.00,
            "current_price": 152.00,
            "stop_loss": 145.00,
            "take_profit": 160.00,
            "status": "OPEN",
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "pnl": 200.00,
            "pnl_percent": 1.33
        },
        {
            "position_id": "pos_002",
            "strategy_id": "strat_001",
            "account_id": "acc_001",
            "signal_id": "sig_entry_1",
            "symbol": "GOOGL",
            "position_type": "LONG",
            "quantity": 50,
            "entry_price": 140.00,
            "current_price": 138.00,
            "stop_loss": 135.00,
            "take_profit": 150.00,
            "status": "OPEN",
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "pnl": -100.00,
            "pnl_percent": -0.71
        }
    ]


@pytest.fixture
def sample_orders_batch() -> List[Dict[str, Any]]:
    """Create batch of sample orders"""
    now = datetime.now(timezone.utc)
    return [
        {
            "order_id": "ord_001",
            "broker_order_id": "IB123456",
            "signal_id": "sig_entry_0",
            "strategy_id": "strat_001",
            "account_id": "acc_001",
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MARKET",
            "status": "FILLED",
            "filled_quantity": 100,
            "avg_fill_price": 150.05,
            "submitted_time": now.isoformat(),
            "filled_time": (now + timedelta(seconds=5)).isoformat()
        },
        {
            "order_id": "ord_002",
            "broker_order_id": "IB123457",
            "signal_id": "sig_entry_1",
            "strategy_id": "strat_001",
            "account_id": "acc_001",
            "symbol": "GOOGL",
            "action": "BUY",
            "quantity": 50,
            "order_type": "LIMIT",
            "limit_price": 140.00,
            "status": "PENDING",
            "filled_quantity": 0,
            "avg_fill_price": None,
            "submitted_time": now.isoformat(),
            "filled_time": None
        },
        {
            "order_id": "ord_003",
            "broker_order_id": "IB123458",
            "signal_id": "sig_exit_0",
            "strategy_id": "strat_001",
            "account_id": "acc_001",
            "symbol": "AAPL",
            "action": "SELL",
            "quantity": 100,
            "order_type": "MARKET",
            "status": "CANCELLED",
            "filled_quantity": 0,
            "avg_fill_price": None,
            "submitted_time": now.isoformat(),
            "cancelled_time": (now + timedelta(seconds=30)).isoformat()
        }
    ]


@pytest.fixture
def populated_test_db(
    test_db,
    sample_signals_batch,
    sample_strategies_batch,
    sample_positions_batch,
    sample_orders_batch
):
    """Populate test database with all sample data"""
    test_db.signals.insert_many(sample_signals_batch)
    test_db.strategies.insert_many(sample_strategies_batch)
    test_db.positions.insert_many(sample_positions_batch)
    test_db.orders.insert_many(sample_orders_batch)
    
    return test_db


@pytest.fixture
def db_query_helpers():
    """Helper functions for database queries"""
    class DBHelpers:
        @staticmethod
        def find_signals_by_status(collection, status: str):
            return list(collection.find({"status": status}))
        
        @staticmethod
        def find_open_positions(collection):
            return list(collection.find({"status": "OPEN"}))
        
        @staticmethod
        def find_active_strategies(collection):
            return list(collection.find({"is_active": True}))
        
        @staticmethod
        def count_by_symbol(collection, symbol: str):
            return collection.count_documents({"symbol": symbol})
        
        @staticmethod
        def get_latest_signal(collection, strategy_id: str):
            return collection.find_one(
                {"strategy_id": strategy_id},
                sort=[("timestamp", -1)]
            )
    
    return DBHelpers()


@pytest.fixture
def db_cleanup_helper(test_db):
    """Helper to clean up specific collections"""
    class CleanupHelper:
        def __init__(self, db):
            self.db = db
        
        def clean_all(self):
            """Clean all collections"""
            for collection_name in self.db.list_collection_names():
                self.db[collection_name].delete_many({})
        
        def clean_test_data(self):
            """Clean only test data (with test prefix)"""
            for collection_name in self.db.list_collection_names():
                self.db[collection_name].delete_many({
                    "$or": [
                        {"signal_id": {"$regex": "^test_"}},
                        {"strategy_id": {"$regex": "^test_"}},
                        {"account_id": {"$regex": "^test_"}},
                    ]
                })
    
    return CleanupHelper(test_db)
