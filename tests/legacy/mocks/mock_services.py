"""
Mock implementations for testing
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock


class MockBrokerGateway:
    """Mock broker gateway for testing"""
    
    def __init__(self):
        self.connected = False
        self.orders: Dict[str, Dict] = {}
        self.positions: Dict[str, Dict] = {}
        self.account_balance = 100000.00
        self.order_counter = 0
    
    def connect(self) -> bool:
        """Mock connection"""
        self.connected = True
        return True
    
    def disconnect(self):
        """Mock disconnection"""
        self.connected = False
    
    def is_connected(self) -> bool:
        """Check connection status"""
        return self.connected
    
    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = "MARKET",
        **kwargs
    ) -> Dict[str, Any]:
        """Mock place order"""
        self.order_counter += 1
        order_id = f"MOCK_ORD_{self.order_counter}"
        
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "status": "SUBMITTED",
            "submitted_time": datetime.now(timezone.utc).isoformat(),
            **kwargs
        }
        
        self.orders[order_id] = order
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Mock cancel order"""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "CANCELLED"
            return True
        return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        return self.orders.get(order_id)
    
    def get_positions(self) -> List[Dict]:
        """Get all positions"""
        return list(self.positions.values())
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for symbol"""
        return self.positions.get(symbol)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        return {
            "account_id": "MOCK_ACCOUNT",
            "balance": self.account_balance,
            "buying_power": self.account_balance * 4,
            "net_liquidation": self.account_balance,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def fill_order(self, order_id: str, price: float):
        """Simulate order fill"""
        if order_id in self.orders:
            order = self.orders[order_id]
            order["status"] = "FILLED"
            order["filled_quantity"] = order["quantity"]
            order["avg_fill_price"] = price
            order["filled_time"] = datetime.now(timezone.utc).isoformat()
            
            # Update positions
            symbol = order["symbol"]
            quantity = order["quantity"] if order["action"] == "BUY" else -order["quantity"]
            
            if symbol in self.positions:
                self.positions[symbol]["quantity"] += quantity
            else:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "avg_cost": price
                }


class MockMongoCollection:
    """Mock MongoDB collection for testing"""
    
    def __init__(self):
        self.documents: List[Dict] = []
    
    def insert_one(self, document: Dict) -> MagicMock:
        """Mock insert one"""
        self.documents.append(document.copy())
        mock_result = MagicMock()
        mock_result.inserted_id = len(self.documents) - 1
        return mock_result
    
    def insert_many(self, documents: List[Dict]) -> MagicMock:
        """Mock insert many"""
        for doc in documents:
            self.documents.append(doc.copy())
        mock_result = MagicMock()
        mock_result.inserted_ids = list(range(len(self.documents) - len(documents), len(self.documents)))
        return mock_result
    
    def find_one(self, filter_dict: Dict = None, **kwargs) -> Optional[Dict]:
        """Mock find one"""
        for doc in self.documents:
            if self._matches_filter(doc, filter_dict or {}):
                return doc.copy()
        return None
    
    def find(self, filter_dict: Dict = None, **kwargs) -> List[Dict]:
        """Mock find"""
        results = []
        for doc in self.documents:
            if self._matches_filter(doc, filter_dict or {}):
                results.append(doc.copy())
        return results
    
    def update_one(self, filter_dict: Dict, update: Dict, **kwargs) -> MagicMock:
        """Mock update one"""
        for i, doc in enumerate(self.documents):
            if self._matches_filter(doc, filter_dict):
                if "$set" in update:
                    doc.update(update["$set"])
                mock_result = MagicMock()
                mock_result.matched_count = 1
                mock_result.modified_count = 1
                return mock_result
        
        mock_result = MagicMock()
        mock_result.matched_count = 0
        mock_result.modified_count = 0
        return mock_result
    
    def delete_one(self, filter_dict: Dict) -> MagicMock:
        """Mock delete one"""
        for i, doc in enumerate(self.documents):
            if self._matches_filter(doc, filter_dict):
                del self.documents[i]
                mock_result = MagicMock()
                mock_result.deleted_count = 1
                return mock_result
        
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        return mock_result
    
    def delete_many(self, filter_dict: Dict) -> MagicMock:
        """Mock delete many"""
        deleted = 0
        self.documents = [
            doc for doc in self.documents
            if not self._matches_filter(doc, filter_dict)
        ]
        mock_result = MagicMock()
        mock_result.deleted_count = deleted
        return mock_result
    
    def count_documents(self, filter_dict: Dict = None) -> int:
        """Mock count documents"""
        count = 0
        for doc in self.documents:
            if self._matches_filter(doc, filter_dict or {}):
                count += 1
        return count
    
    def _matches_filter(self, document: Dict, filter_dict: Dict) -> bool:
        """Check if document matches filter"""
        if not filter_dict:
            return True
        
        for key, value in filter_dict.items():
            if key not in document or document[key] != value:
                return False
        return True


class MockSignalProcessor:
    """Mock signal processor for testing"""
    
    def __init__(self):
        self.processed_signals = []
    
    def process_signal(self, signal: Dict) -> Dict:
        """Mock process signal"""
        enriched_signal = signal.copy()
        enriched_signal["processed"] = True
        enriched_signal["processed_at"] = datetime.now(timezone.utc).isoformat()
        self.processed_signals.append(enriched_signal)
        return enriched_signal
    
    def validate_signal(self, signal: Dict) -> bool:
        """Mock validate signal"""
        required_fields = ["signal_id", "strategy_id", "symbol", "action"]
        return all(field in signal for field in required_fields)


class MockExecutionEngine:
    """Mock execution engine for testing"""
    
    def __init__(self):
        self.executed_orders = []
        self.broker = MockBrokerGateway()
    
    def execute_signal(self, signal: Dict) -> Dict:
        """Mock execute signal"""
        order = self.broker.place_order(
            symbol=signal["symbol"],
            action="BUY" if signal["action"] == "ENTRY" else "SELL",
            quantity=signal.get("quantity", 100),
            order_type="MARKET"
        )
        
        self.executed_orders.append(order)
        return order
    
    def get_execution_status(self, order_id: str) -> Optional[Dict]:
        """Get execution status"""
        return self.broker.get_order_status(order_id)


class MockMarketDataProvider:
    """Mock market data provider"""
    
    def __init__(self):
        self.price_data = {
            "AAPL": 150.00,
            "GOOGL": 140.00,
            "MSFT": 380.00,
            "TSLA": 250.00,
        }
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        return self.price_data.get(symbol, 100.00)
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get full quote for symbol"""
        price = self.get_current_price(symbol)
        return {
            "symbol": symbol,
            "last": price,
            "bid": price - 0.05,
            "ask": price + 0.05,
            "volume": 1000000,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def update_price(self, symbol: str, price: float):
        """Update price for testing"""
        self.price_data[symbol] = price
