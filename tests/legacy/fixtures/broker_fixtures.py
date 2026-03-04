"""
Test fixtures for broker-related tests
Provides mocks and fixtures for IBKR and other broker integrations
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, AsyncMock
import pytest


@pytest.fixture
def mock_ib_insync():
    """Mock ib_insync module"""
    mock_module = MagicMock()
    
    # Mock IB class
    mock_ib = MagicMock()
    mock_ib.isConnected.return_value = True
    mock_ib.client.serverVersion.return_value = 176
    mock_module.IB.return_value = mock_ib
    
    # Mock Stock class
    mock_module.Stock = MagicMock
    
    # Mock Order classes
    mock_module.MarketOrder = MagicMock
    mock_module.LimitOrder = MagicMock
    mock_module.StopOrder = MagicMock
    
    return mock_module


@pytest.fixture
def mock_ibkr_gateway():
    """Mock IBKR Gateway with realistic responses"""
    gateway = MagicMock()
    
    # Connection methods
    gateway.connect.return_value = True
    gateway.disconnect.return_value = None
    gateway.is_connected.return_value = True
    
    # Market data methods
    def mock_get_market_data(symbol: str):
        return {
            "symbol": symbol,
            "last": 150.00,
            "bid": 149.95,
            "ask": 150.05,
            "volume": 1000000,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    gateway.get_market_data.side_effect = mock_get_market_data
    
    # Order methods
    def mock_place_order(symbol: str, action: str, quantity: int, **kwargs):
        return {
            "order_id": f"IB{datetime.now().timestamp():.0f}",
            "status": "SUBMITTED",
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "submitted_time": datetime.now(timezone.utc).isoformat()
        }
    
    gateway.place_order.side_effect = mock_place_order
    gateway.cancel_order.return_value = True
    
    # Position methods
    gateway.get_positions.return_value = []
    gateway.get_position.return_value = None
    
    # Account methods
    gateway.get_account_info.return_value = {
        "account_id": "DU123456",
        "balance": 100000.00,
        "buying_power": 400000.00,
        "net_liquidation": 100000.00,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return gateway


@pytest.fixture
def sample_ibkr_order_filled():
    """Sample filled IBKR order"""
    return {
        "order_id": "IB123456",
        "perm_id": 1234567890,
        "client_id": 1,
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
        "filled_quantity": 100,
        "order_type": "MARKET",
        "status": "FILLED",
        "avg_fill_price": 150.05,
        "commission": 1.00,
        "submitted_time": "2026-01-20T12:00:00Z",
        "filled_time": "2026-01-20T12:00:05Z"
    }


@pytest.fixture
def sample_ibkr_order_pending():
    """Sample pending IBKR order"""
    return {
        "order_id": "IB123457",
        "perm_id": 1234567891,
        "client_id": 1,
        "symbol": "AAPL",
        "action": "SELL",
        "quantity": 100,
        "filled_quantity": 0,
        "order_type": "LIMIT",
        "limit_price": 155.00,
        "status": "SUBMITTED",
        "avg_fill_price": None,
        "commission": None,
        "submitted_time": "2026-01-20T12:00:00Z",
        "filled_time": None
    }


@pytest.fixture
def sample_ibkr_position():
    """Sample IBKR position"""
    return {
        "symbol": "AAPL",
        "position": 100,
        "avg_cost": 150.00,
        "market_value": 15200.00,
        "unrealized_pnl": 200.00,
        "realized_pnl": 0.00,
        "account": "DU123456"
    }


@pytest.fixture
def sample_ibkr_account_values():
    """Sample IBKR account values"""
    return {
        "NetLiquidation": 100000.00,
        "TotalCashValue": 95000.00,
        "GrossPositionValue": 5000.00,
        "BuyingPower": 400000.00,
        "AvailableFunds": 95000.00,
        "ExcessLiquidity": 95000.00,
        "DayTradesRemaining": 3,
        "Leverage": 4.0
    }


@pytest.fixture
def mock_broker_connection_config():
    """Mock broker connection configuration"""
    return {
        "broker": "IBKR",
        "host": "localhost",
        "port": 4004,
        "client_id": 1,
        "account": "DU123456",
        "timeout": 10,
        "retry_attempts": 3,
        "retry_delay": 1
    }


@pytest.fixture
async def mock_async_broker_gateway():
    """Mock async broker gateway"""
    gateway = AsyncMock()
    
    gateway.connect.return_value = True
    gateway.disconnect.return_value = None
    gateway.is_connected.return_value = True
    
    async def mock_place_order_async(symbol: str, action: str, quantity: int, **kwargs):
        return {
            "order_id": f"IB{datetime.now().timestamp():.0f}",
            "status": "SUBMITTED",
            "symbol": symbol,
            "action": action,
            "quantity": quantity
        }
    
    gateway.place_order.side_effect = mock_place_order_async
    gateway.get_positions.return_value = []
    
    return gateway


@pytest.fixture
def broker_error_responses():
    """Common broker error responses"""
    return {
        "connection_refused": {
            "error": "ConnectionRefusedError",
            "message": "Failed to connect to broker gateway",
            "code": "CONN_001"
        },
        "authentication_failed": {
            "error": "AuthenticationError",
            "message": "Invalid credentials",
            "code": "AUTH_001"
        },
        "order_rejected": {
            "error": "OrderRejected",
            "message": "Order rejected by broker",
            "code": "ORD_001",
            "details": "Insufficient funds"
        },
        "rate_limit": {
            "error": "RateLimitExceeded",
            "message": "Too many requests",
            "code": "RATE_001",
            "retry_after": 60
        },
        "market_closed": {
            "error": "MarketClosed",
            "message": "Market is closed",
            "code": "MKT_001"
        }
    }


@pytest.fixture
def mock_market_data_tick():
    """Mock real-time market data tick"""
    def create_tick(symbol: str, price: float):
        return {
            "symbol": symbol,
            "last": price,
            "bid": price - 0.05,
            "ask": price + 0.05,
            "bid_size": 100,
            "ask_size": 100,
            "volume": 1000000,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    return create_tick


@pytest.fixture
def mock_historical_data():
    """Mock historical market data"""
    def create_historical(symbol: str, days: int = 30):
        from datetime import timedelta
        data = []
        base_price = 150.00
        
        for i in range(days):
            date = datetime.now(timezone.utc) - timedelta(days=days - i)
            data.append({
                "symbol": symbol,
                "date": date.isoformat(),
                "open": base_price + (i % 5),
                "high": base_price + (i % 5) + 2,
                "low": base_price + (i % 5) - 2,
                "close": base_price + (i % 5) + 1,
                "volume": 1000000 + (i * 10000)
            })
        
        return data
    
    return create_historical
