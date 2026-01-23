"""
Test helper utilities
Provides common helper functions for testing
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import random


class SignalGenerator:
    """Generate test signals"""
    
    def __init__(self, strategy_id: str = "test_strategy"):
        self.strategy_id = strategy_id
        self.signal_counter = 0
    
    def generate_entry_signal(
        self,
        symbol: str,
        signal_type: str = "LONG",
        price: float = None,
        quantity: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate entry signal"""
        self.signal_counter += 1
        
        if price is None:
            price = random.uniform(100, 200)
        
        signal = {
            "signal_id": f"sig_{self.signal_counter}_{int(datetime.now().timestamp())}",
            "strategy_id": self.strategy_id,
            "symbol": symbol,
            "action": "ENTRY",
            "signal_type": signal_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": price,
            "quantity": quantity,
            "status": "PENDING",
            "metadata": {}
        }
        
        # Add stop loss and take profit
        if signal_type == "LONG":
            signal["stop_loss"] = price * 0.97  # 3% stop loss
            signal["take_profit"] = price * 1.05  # 5% take profit
        else:  # SHORT
            signal["stop_loss"] = price * 1.03
            signal["take_profit"] = price * 0.95
        
        # Merge additional kwargs
        signal.update(kwargs)
        
        return signal
    
    def generate_exit_signal(
        self,
        symbol: str,
        signal_type: str = "LONG",
        price: float = None,
        quantity: int = 100,
        reason: str = "manual",
        **kwargs
    ) -> Dict[str, Any]:
        """Generate exit signal"""
        self.signal_counter += 1
        
        if price is None:
            price = random.uniform(100, 200)
        
        signal = {
            "signal_id": f"sig_{self.signal_counter}_{int(datetime.now().timestamp())}",
            "strategy_id": self.strategy_id,
            "symbol": symbol,
            "action": "EXIT",
            "signal_type": signal_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": price,
            "quantity": quantity,
            "status": "PENDING",
            "metadata": {
                "exit_reason": reason
            }
        }
        
        signal.update(kwargs)
        
        return signal
    
    def generate_signal_pair(
        self,
        symbol: str,
        signal_type: str = "LONG",
        entry_price: float = None,
        exit_price: float = None,
        time_gap_minutes: int = 60
    ) -> tuple[Dict, Dict]:
        """Generate entry and exit signal pair"""
        entry = self.generate_entry_signal(symbol, signal_type, entry_price)
        
        # Wait time between signals
        exit_time = datetime.fromisoformat(entry["timestamp"]) + timedelta(minutes=time_gap_minutes)
        
        exit_signal = self.generate_exit_signal(symbol, signal_type, exit_price)
        exit_signal["timestamp"] = exit_time.isoformat()
        
        return entry, exit_signal


class TestDataGenerator:
    """Generate various test data"""
    
    @staticmethod
    def generate_strategy(
        strategy_id: str = None,
        trading_mode: str = "LIVE_PAPER",
        is_active: bool = True
    ) -> Dict[str, Any]:
        """Generate test strategy"""
        if strategy_id is None:
            strategy_id = f"strat_{int(datetime.now().timestamp())}"
        
        return {
            "strategy_id": strategy_id,
            "strategy_name": f"Test Strategy {strategy_id}",
            "is_active": is_active,
            "trading_mode": trading_mode,
            "symbols": ["AAPL", "GOOGL", "MSFT"],
            "max_position_size": 10000,
            "risk_per_trade": 0.02,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        }
    
    @staticmethod
    def generate_account(
        account_id: str = None,
        broker: str = "IBKR",
        account_type: str = "PAPER"
    ) -> Dict[str, Any]:
        """Generate test account"""
        if account_id is None:
            account_id = f"acc_{int(datetime.now().timestamp())}"
        
        return {
            "account_id": account_id,
            "account_name": f"Test Account {account_id}",
            "broker": broker,
            "account_type": account_type,
            "is_active": True,
            "initial_balance": 100000.00,
            "current_balance": 100000.00,
            "credentials": {
                "host": "localhost",
                "port": 4004,
                "client_id": random.randint(1, 999)
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def generate_position(
        symbol: str,
        quantity: int = 100,
        entry_price: float = 150.00,
        status: str = "OPEN"
    ) -> Dict[str, Any]:
        """Generate test position"""
        return {
            "position_id": f"pos_{int(datetime.now().timestamp())}",
            "strategy_id": "test_strategy",
            "account_id": "test_account",
            "signal_id": "test_signal",
            "symbol": symbol,
            "position_type": "LONG",
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": entry_price * 1.02,
            "stop_loss": entry_price * 0.97,
            "take_profit": entry_price * 1.05,
            "status": status,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "pnl": (entry_price * 1.02 - entry_price) * quantity,
            "pnl_percent": 2.0
        }
    
    @staticmethod
    def generate_order(
        symbol: str,
        action: str = "BUY",
        quantity: int = 100,
        status: str = "FILLED"
    ) -> Dict[str, Any]:
        """Generate test order"""
        now = datetime.now(timezone.utc)
        
        order = {
            "order_id": f"ord_{int(now.timestamp())}",
            "broker_order_id": f"IB{random.randint(100000, 999999)}",
            "signal_id": "test_signal",
            "strategy_id": "test_strategy",
            "account_id": "test_account",
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": "MARKET",
            "status": status,
            "submitted_time": now.isoformat()
        }
        
        if status == "FILLED":
            order.update({
                "filled_quantity": quantity,
                "avg_fill_price": 150.00,
                "filled_time": (now + timedelta(seconds=5)).isoformat()
            })
        
        return order


class FileHelper:
    """Helper for file operations in tests"""
    
    @staticmethod
    def save_json(data: Dict, file_path: Path):
        """Save data to JSON file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def load_json(file_path: Path) -> Dict:
        """Load data from JSON file"""
        with open(file_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def create_temp_file(content: str, suffix: str = ".txt") -> Path:
        """Create temporary file with content"""
        import tempfile
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return Path(path)
    
    @staticmethod
    def cleanup_temp_file(file_path: Path):
        """Clean up temporary file"""
        if file_path.exists():
            file_path.unlink()


class AssertionHelper:
    """Helper for complex assertions"""
    
    @staticmethod
    def assert_signal_valid(signal: Dict):
        """Assert signal has required fields"""
        required_fields = [
            "signal_id", "strategy_id", "symbol", 
            "action", "timestamp", "status"
        ]
        for field in required_fields:
            assert field in signal, f"Missing required field: {field}"
    
    @staticmethod
    def assert_order_valid(order: Dict):
        """Assert order has required fields"""
        required_fields = [
            "order_id", "symbol", "action", 
            "quantity", "status", "submitted_time"
        ]
        for field in required_fields:
            assert field in order, f"Missing required field: {field}"
    
    @staticmethod
    def assert_position_valid(position: Dict):
        """Assert position has required fields"""
        required_fields = [
            "position_id", "symbol", "quantity",
            "entry_price", "status", "entry_time"
        ]
        for field in required_fields:
            assert field in position, f"Missing required field: {field}"
    
    @staticmethod
    def assert_datetime_recent(dt_string: str, max_age_seconds: int = 60):
        """Assert datetime is recent"""
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        age = (now - dt).total_seconds()
        assert age <= max_age_seconds, f"Datetime too old: {age} seconds"
    
    @staticmethod
    def assert_dict_contains(actual: Dict, expected: Dict):
        """Assert dict contains expected key-value pairs"""
        for key, value in expected.items():
            assert key in actual, f"Missing key: {key}"
            assert actual[key] == value, f"Value mismatch for {key}: {actual[key]} != {value}"


class WaitHelper:
    """Helper for waiting in tests"""
    
    @staticmethod
    def wait_for_condition(
        condition_func,
        timeout: float = 10.0,
        interval: float = 0.1,
        error_message: str = "Condition not met"
    ):
        """Wait for condition to become true"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        
        raise TimeoutError(error_message)
    
    @staticmethod
    def wait_for_document(
        collection,
        filter_dict: Dict,
        timeout: float = 10.0
    ):
        """Wait for document to appear in collection"""
        def check():
            return collection.find_one(filter_dict) is not None
        
        WaitHelper.wait_for_condition(
            check,
            timeout=timeout,
            error_message=f"Document not found: {filter_dict}"
        )


class ComparisonHelper:
    """Helper for comparing complex objects"""
    
    @staticmethod
    def compare_signals(signal1: Dict, signal2: Dict, ignore_fields: List[str] = None) -> bool:
        """Compare two signals, optionally ignoring certain fields"""
        if ignore_fields is None:
            ignore_fields = ["timestamp", "_id"]
        
        s1 = {k: v for k, v in signal1.items() if k not in ignore_fields}
        s2 = {k: v for k, v in signal2.items() if k not in ignore_fields}
        
        return s1 == s2
    
    @staticmethod
    def find_differences(dict1: Dict, dict2: Dict) -> Dict[str, tuple]:
        """Find differences between two dictionaries"""
        differences = {}
        
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            val1 = dict1.get(key)
            val2 = dict2.get(key)
            
            if val1 != val2:
                differences[key] = (val1, val2)
        
        return differences
