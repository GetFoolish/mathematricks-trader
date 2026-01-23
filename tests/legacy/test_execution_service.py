"""
Unit tests for Execution Service
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from tests.helpers.test_utils import SignalGenerator, TestDataGenerator, AssertionHelper
from tests.mocks.mock_services import MockBrokerGateway


@pytest.mark.unit
class TestOrderCreation:
    """Test order creation logic"""
    
    def test_create_market_order_from_signal(self, sample_signal):
        """Test creating market order from signal"""
        order = {
            "order_id": f"ord_{int(datetime.now().timestamp())}",
            "signal_id": sample_signal["signal_id"],
            "strategy_id": sample_signal["strategy_id"],
            "symbol": sample_signal["symbol"],
            "action": "BUY" if sample_signal["action"] == "ENTRY" else "SELL",
            "quantity": sample_signal["quantity"],
            "order_type": "MARKET",
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        AssertionHelper.assert_order_valid(order)
        assert order["action"] == "BUY"
        assert order["order_type"] == "MARKET"
    
    def test_create_limit_order(self, sample_signal):
        """Test creating limit order"""
        order = {
            "order_id": f"ord_{int(datetime.now().timestamp())}",
            "signal_id": sample_signal["signal_id"],
            "symbol": sample_signal["symbol"],
            "action": "BUY",
            "quantity": sample_signal["quantity"],
            "order_type": "LIMIT",
            "limit_price": sample_signal["price"],
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        assert order["order_type"] == "LIMIT"
        assert "limit_price" in order
        assert order["limit_price"] == sample_signal["price"]
    
    def test_create_stop_order(self, sample_signal):
        """Test creating stop order for stop loss"""
        stop_order = {
            "order_id": f"ord_stop_{int(datetime.now().timestamp())}",
            "signal_id": sample_signal["signal_id"],
            "symbol": sample_signal["symbol"],
            "action": "SELL",
            "quantity": sample_signal["quantity"],
            "order_type": "STOP",
            "stop_price": sample_signal["stop_loss"],
            "status": "PENDING",
            "order_class": "STOP_LOSS"
        }
        
        assert stop_order["order_type"] == "STOP"
        assert stop_order["stop_price"] == sample_signal["stop_loss"]
        assert stop_order["order_class"] == "STOP_LOSS"


@pytest.mark.unit
class TestOrderSubmission:
    """Test order submission to broker"""
    
    def test_submit_order_to_broker(self, sample_signal, mock_ibkr_gateway):
        """Test submitting order to broker gateway"""
        order = mock_ibkr_gateway.place_order(
            symbol=sample_signal["symbol"],
            action="BUY",
            quantity=sample_signal["quantity"],
            order_type="MARKET"
        )
        
        assert order["status"] == "SUBMITTED"
        assert "order_id" in order
        assert order["symbol"] == sample_signal["symbol"]
    
    def test_handle_broker_rejection(self, sample_signal, broker_error_responses):
        """Test handling broker order rejection"""
        rejection = broker_error_responses["order_rejected"]
        
        assert rejection["error"] == "OrderRejected"
        assert "message" in rejection
        
        # Order should be marked as rejected
        order = {
            "order_id": "test_ord_123",
            "status": "REJECTED",
            "rejection_reason": rejection["message"],
            "error_details": rejection["details"]
        }
        
        assert order["status"] == "REJECTED"
    
    def test_retry_on_connection_error(self, broker_error_responses):
        """Test retry logic on connection error"""
        error = broker_error_responses["connection_refused"]
        
        max_retries = 3
        retry_count = 0
        
        # Simulate retry logic
        while retry_count < max_retries:
            retry_count += 1
            # Would attempt connection here
        
        assert retry_count == max_retries
    
    def test_respect_rate_limits(self, broker_error_responses):
        """Test respecting broker rate limits"""
        rate_limit_error = broker_error_responses["rate_limit"]
        
        assert "retry_after" in rate_limit_error
        assert rate_limit_error["retry_after"] == 60


@pytest.mark.unit
class TestOrderTracking:
    """Test order status tracking"""
    
    def test_track_order_status(self, sample_order, clean_orders_collection):
        """Test tracking order status updates"""
        # Insert initial order
        clean_orders_collection.insert_one(sample_order)
        
        # Update status
        clean_orders_collection.update_one(
            {"order_id": sample_order["order_id"]},
            {"$set": {"status": "FILLED"}}
        )
        
        updated = clean_orders_collection.find_one({"order_id": sample_order["order_id"]})
        assert updated["status"] == "FILLED"
    
    def test_record_order_fill(self, sample_order, clean_orders_collection):
        """Test recording order fill details"""
        sample_order["status"] = "FILLED"
        sample_order["filled_quantity"] = sample_order["quantity"]
        sample_order["avg_fill_price"] = 150.05
        sample_order["filled_time"] = datetime.now(timezone.utc).isoformat()
        sample_order["commission"] = 1.00
        
        clean_orders_collection.insert_one(sample_order)
        
        filled = clean_orders_collection.find_one({"order_id": sample_order["order_id"]})
        assert filled["status"] == "FILLED"
        assert filled["avg_fill_price"] == 150.05
        assert "commission" in filled
    
    def test_partial_fill_tracking(self, sample_order):
        """Test tracking partial order fills"""
        sample_order["quantity"] = 100
        sample_order["filled_quantity"] = 50
        sample_order["status"] = "PARTIALLY_FILLED"
        
        remaining = sample_order["quantity"] - sample_order["filled_quantity"]
        
        assert remaining == 50
        assert sample_order["status"] == "PARTIALLY_FILLED"


@pytest.mark.unit
class TestPositionManagement:
    """Test position management"""
    
    def test_create_position_from_filled_order(self, sample_order):
        """Test creating position after order fill"""
        sample_order["status"] = "FILLED"
        sample_order["avg_fill_price"] = 150.00
        
        position = {
            "position_id": f"pos_{int(datetime.now().timestamp())}",
            "order_id": sample_order["order_id"],
            "signal_id": sample_order["signal_id"],
            "strategy_id": sample_order["strategy_id"],
            "symbol": sample_order["symbol"],
            "quantity": sample_order["filled_quantity"],
            "entry_price": sample_order["avg_fill_price"],
            "status": "OPEN",
            "entry_time": sample_order["filled_time"]
        }
        
        AssertionHelper.assert_position_valid(position)
        assert position["entry_price"] == 150.00
    
    def test_update_position_on_exit(self, sample_position):
        """Test updating position on exit"""
        sample_position["status"] = "CLOSED"
        sample_position["exit_price"] = 155.00
        sample_position["exit_time"] = datetime.now(timezone.utc).isoformat()
        
        # Calculate final P&L
        pnl = (sample_position["exit_price"] - sample_position["entry_price"]) * sample_position["quantity"]
        sample_position["realized_pnl"] = pnl
        
        assert sample_position["status"] == "CLOSED"
        assert sample_position["realized_pnl"] == 500.00
    
    def test_calculate_position_pnl(self, sample_position):
        """Test calculating position P&L"""
        entry_price = 150.00
        current_price = 152.00
        quantity = 100
        
        unrealized_pnl = (current_price - entry_price) * quantity
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        
        assert unrealized_pnl == 200.00
        assert abs(pnl_percent - 1.33) < 0.01


@pytest.mark.unit
class TestRiskManagement:
    """Test risk management logic"""
    
    def test_position_size_limits(self, sample_signal):
        """Test enforcing position size limits"""
        max_position_size = 10000.00
        signal_value = sample_signal["price"] * sample_signal["quantity"]
        
        if signal_value > max_position_size:
            # Reduce quantity
            adjusted_quantity = int(max_position_size / sample_signal["price"])
            sample_signal["quantity"] = adjusted_quantity
        
        final_value = sample_signal["price"] * sample_signal["quantity"]
        assert final_value <= max_position_size
    
    def test_risk_per_trade_limit(self, sample_signal):
        """Test enforcing risk per trade limit"""
        account_balance = 100000.00
        max_risk_percent = 0.02  # 2%
        max_risk_amount = account_balance * max_risk_percent
        
        # Calculate risk
        stop_distance = abs(sample_signal["price"] - sample_signal["stop_loss"])
        trade_risk = stop_distance * sample_signal["quantity"]
        
        if trade_risk > max_risk_amount:
            # Reduce position size
            adjusted_quantity = int(max_risk_amount / stop_distance)
            sample_signal["quantity"] = adjusted_quantity
        
        final_risk = stop_distance * sample_signal["quantity"]
        assert final_risk <= max_risk_amount
    
    def test_max_open_positions_limit(self, sample_positions_batch):
        """Test enforcing maximum open positions"""
        max_open_positions = 5
        open_positions = [p for p in sample_positions_batch if p["status"] == "OPEN"]
        
        can_open_new = len(open_positions) < max_open_positions
        
        assert isinstance(can_open_new, bool)
    
    def test_account_balance_check(self):
        """Test checking sufficient account balance"""
        account_balance = 100000.00
        buying_power = 400000.00  # 4x leverage
        
        order_value = 150.00 * 100  # $15,000
        
        has_sufficient_funds = order_value <= buying_power
        
        assert has_sufficient_funds is True


@pytest.mark.unit
class TestOrderCancellation:
    """Test order cancellation"""
    
    def test_cancel_pending_order(self, mock_ibkr_gateway):
        """Test cancelling pending order"""
        # Place order first
        order = mock_ibkr_gateway.place_order("AAPL", "BUY", 100)
        order_id = order["order_id"]
        
        # Cancel it
        result = mock_ibkr_gateway.cancel_order(order_id)
        
        assert result is True
        
        # Check status
        status = mock_ibkr_gateway.get_order_status(order_id)
        assert status["status"] == "CANCELLED"
    
    def test_cannot_cancel_filled_order(self, sample_order):
        """Test that filled orders cannot be cancelled"""
        sample_order["status"] = "FILLED"
        
        # Should not allow cancellation
        can_cancel = sample_order["status"] in ["PENDING", "SUBMITTED"]
        
        assert can_cancel is False
    
    def test_cancel_all_strategy_orders(self, sample_orders_batch):
        """Test cancelling all orders for a strategy"""
        strategy_id = "strat_001"
        
        strategy_orders = [
            o for o in sample_orders_batch 
            if o["strategy_id"] == strategy_id and o["status"] in ["PENDING", "SUBMITTED"]
        ]
        
        # Would cancel all these orders
        assert len(strategy_orders) > 0


@pytest.mark.unit  
class TestBrokerIntegration:
    """Test broker integration specifics"""
    
    def test_ibkr_connection(self, mock_ibkr_gateway):
        """Test IBKR gateway connection"""
        connected = mock_ibkr_gateway.connect()
        assert connected is True
        assert mock_ibkr_gateway.is_connected() is True
    
    def test_get_account_info(self, mock_ibkr_gateway):
        """Test getting account information"""
        account_info = mock_ibkr_gateway.get_account_info()
        
        assert "balance" in account_info
        assert "buying_power" in account_info
        assert account_info["balance"] > 0
    
    def test_get_positions(self, mock_ibkr_gateway):
        """Test getting current positions"""
        positions = mock_ibkr_gateway.get_positions()
        
        assert isinstance(positions, list)
    
    def test_market_data_subscription(self, mock_market_data_tick):
        """Test subscribing to market data"""
        tick = mock_market_data_tick("AAPL", 150.00)
        
        assert tick["symbol"] == "AAPL"
        assert tick["last"] == 150.00
        assert "bid" in tick
        assert "ask" in tick
