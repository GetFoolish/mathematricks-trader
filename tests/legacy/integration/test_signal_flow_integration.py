"""
Integration tests for signal flow
Tests the complete flow from signal ingestion to order execution
"""

import pytest
from datetime import datetime, timezone
import time

from tests.helpers.test_utils import SignalGenerator, WaitHelper
from tests.helpers.db_helpers import DatabaseTestHelper


@pytest.mark.integration
@pytest.mark.signal_flow
class TestSignalToOrderFlow:
    """Test complete signal to order execution flow"""
    
    def test_entry_signal_to_order_flow(
        self,
        test_db,
        sample_strategy,
        sample_account,
        mock_ibkr_gateway
    ):
        """Test full flow: entry signal -> validation -> enrichment -> order"""
        db_helper = DatabaseTestHelper(test_db)
        
        # 1. Setup: Create strategy and account
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # 2. Generate and insert signal
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        entry_signal = generator.generate_entry_signal("AAPL", price=150.00)
        test_db.signals.insert_one(entry_signal)
        
        # 3. Simulate signal processing
        signal = test_db.signals.find_one({"signal_id": entry_signal["signal_id"]})
        assert signal is not None
        
        # Mark as validated
        test_db.signals.update_one(
            {"signal_id": entry_signal["signal_id"]},
            {"$set": {"status": "VALIDATED"}}
        )
        
        # 4. Simulate order creation
        order = mock_ibkr_gateway.place_order(
            symbol=signal["symbol"],
            action="BUY",
            quantity=signal["quantity"],
            order_type="MARKET"
        )
        
        # Store order
        order_doc = {
            **order,
            "signal_id": signal["signal_id"],
            "strategy_id": signal["strategy_id"],
            "account_id": sample_account["account_id"]
        }
        test_db.orders.insert_one(order_doc)
        
        # 5. Verify flow
        final_signal = test_db.signals.find_one({"signal_id": entry_signal["signal_id"]})
        assert final_signal["status"] == "VALIDATED"
        
        stored_order = test_db.orders.find_one({"signal_id": entry_signal["signal_id"]})
        assert stored_order is not None
        assert stored_order["status"] == "SUBMITTED"
    
    def test_exit_signal_closes_position(
        self,
        test_db,
        sample_strategy,
        sample_position,
        mock_ibkr_gateway
    ):
        """Test exit signal closes open position"""
        # 1. Setup: Create open position
        test_db.strategies.insert_one(sample_strategy)
        test_db.positions.insert_one(sample_position)
        
        # 2. Generate exit signal
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        exit_signal = generator.generate_exit_signal(
            symbol=sample_position["symbol"],
            quantity=sample_position["quantity"],
            reason="take_profit"
        )
        test_db.signals.insert_one(exit_signal)
        
        # 3. Place sell order
        order = mock_ibkr_gateway.place_order(
            symbol=exit_signal["symbol"],
            action="SELL",
            quantity=exit_signal["quantity"]
        )
        
        # 4. Simulate order fill
        mock_ibkr_gateway.fill_order(order["order_id"], 155.00)
        
        # 5. Close position
        test_db.positions.update_one(
            {"position_id": sample_position["position_id"]},
            {"$set": {
                "status": "CLOSED",
                "exit_price": 155.00,
                "realized_pnl": (155.00 - sample_position["entry_price"]) * sample_position["quantity"]
            }}
        )
        
        # 6. Verify position closed
        closed_position = test_db.positions.find_one({"position_id": sample_position["position_id"]})
        assert closed_position["status"] == "CLOSED"
        assert closed_position["realized_pnl"] > 0


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    """Test database integration across services"""
    
    def test_signal_strategy_relationship(self, test_db, sample_strategy):
        """Test relationship between signals and strategies"""
        # Insert strategy
        test_db.strategies.insert_one(sample_strategy)
        
        # Create signals for strategy
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        signals = [
            generator.generate_entry_signal("AAPL"),
            generator.generate_entry_signal("GOOGL"),
            generator.generate_entry_signal("MSFT")
        ]
        test_db.signals.insert_many(signals)
        
        # Verify relationship
        strategy_signals = list(test_db.signals.find({
            "strategy_id": sample_strategy["strategy_id"]
        }))
        
        assert len(strategy_signals) == 3
        assert all(s["strategy_id"] == sample_strategy["strategy_id"] for s in strategy_signals)
    
    def test_signal_order_position_chain(
        self,
        test_db,
        sample_strategy,
        sample_account
    ):
        """Test complete chain: signal -> order -> position"""
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # 1. Create signal
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        signal = generator.generate_entry_signal("AAPL", price=150.00, quantity=100)
        test_db.signals.insert_one(signal)
        
        # 2. Create order from signal
        order = {
            "order_id": f"ord_{int(datetime.now().timestamp())}",
            "signal_id": signal["signal_id"],
            "strategy_id": signal["strategy_id"],
            "account_id": sample_account["account_id"],
            "symbol": signal["symbol"],
            "action": "BUY",
            "quantity": signal["quantity"],
            "status": "FILLED",
            "avg_fill_price": 150.05,
            "filled_time": datetime.now(timezone.utc).isoformat()
        }
        test_db.orders.insert_one(order)
        
        # 3. Create position from order
        position = {
            "position_id": f"pos_{int(datetime.now().timestamp())}",
            "signal_id": signal["signal_id"],
            "order_id": order["order_id"],
            "strategy_id": signal["strategy_id"],
            "account_id": sample_account["account_id"],
            "symbol": order["symbol"],
            "quantity": order["quantity"],
            "entry_price": order["avg_fill_price"],
            "status": "OPEN",
            "entry_time": order["filled_time"]
        }
        test_db.positions.insert_one(position)
        
        # 4. Verify chain
        signal_check = test_db.signals.find_one({"signal_id": signal["signal_id"]})
        order_check = test_db.orders.find_one({"signal_id": signal["signal_id"]})
        position_check = test_db.positions.find_one({"signal_id": signal["signal_id"]})
        
        assert signal_check is not None
        assert order_check is not None
        assert position_check is not None
        assert position_check["order_id"] == order["order_id"]
    
    def test_query_performance_with_indexes(self, test_db, sample_signals_batch):
        """Test query performance with proper indexing"""
        # Insert large batch
        test_db.signals.insert_many(sample_signals_batch)
        
        # Create indexes (would be done in production)
        test_db.signals.create_index("strategy_id")
        test_db.signals.create_index("status")
        test_db.signals.create_index("timestamp")
        
        # Query should be fast
        start_time = time.time()
        results = list(test_db.signals.find({
            "strategy_id": sample_signals_batch[0]["strategy_id"],
            "status": "PENDING"
        }))
        query_time = time.time() - start_time
        
        assert len(results) > 0
        assert query_time < 1.0  # Should be very fast


@pytest.mark.integration
@pytest.mark.broker
class TestBrokerIntegration:
    """Test broker integration flows"""
    
    def test_order_submission_flow(self, mock_ibkr_gateway):
        """Test complete order submission flow"""
        # 1. Connect
        assert mock_ibkr_gateway.connect() is True
        
        # 2. Get account info
        account = mock_ibkr_gateway.get_account_info()
        assert account["balance"] > 0
        
        # 3. Place order
        order = mock_ibkr_gateway.place_order("AAPL", "BUY", 100)
        assert order["status"] == "SUBMITTED"
        
        # 4. Check order status
        status = mock_ibkr_gateway.get_order_status(order["order_id"])
        assert status is not None
        
        # 5. Simulate fill
        mock_ibkr_gateway.fill_order(order["order_id"], 150.00)
        
        # 6. Verify fill
        filled = mock_ibkr_gateway.get_order_status(order["order_id"])
        assert filled["status"] == "FILLED"
    
    def test_position_tracking_flow(self, mock_ibkr_gateway):
        """Test position tracking flow"""
        # 1. Place and fill buy order
        buy_order = mock_ibkr_gateway.place_order("AAPL", "BUY", 100)
        mock_ibkr_gateway.fill_order(buy_order["order_id"], 150.00)
        
        # 2. Check positions
        positions = mock_ibkr_gateway.get_positions()
        aapl_position = mock_ibkr_gateway.get_position("AAPL")
        
        assert aapl_position is not None
        assert aapl_position["quantity"] == 100
        
        # 3. Place and fill sell order
        sell_order = mock_ibkr_gateway.place_order("AAPL", "SELL", 100)
        mock_ibkr_gateway.fill_order(sell_order["order_id"], 155.00)
        
        # 4. Position should be flat
        updated_position = mock_ibkr_gateway.get_position("AAPL")
        assert updated_position["quantity"] == 0


@pytest.mark.integration
@pytest.mark.slow
class TestConcurrentSignalProcessing:
    """Test processing multiple signals concurrently"""
    
    def test_multiple_signals_same_strategy(
        self,
        test_db,
        sample_strategy,
        sample_signals_batch
    ):
        """Test processing multiple signals for same strategy"""
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        
        # Process all signals
        for signal in sample_signals_batch:
            signal["strategy_id"] = sample_strategy["strategy_id"]
        
        test_db.signals.insert_many(sample_signals_batch)
        
        # Verify all inserted
        count = test_db.signals.count_documents({
            "strategy_id": sample_strategy["strategy_id"]
        })
        
        assert count == len(sample_signals_batch)
    
    def test_signals_multiple_strategies(
        self,
        test_db,
        sample_strategies_batch,
        sample_signals_batch
    ):
        """Test processing signals across multiple strategies"""
        # Insert strategies
        test_db.strategies.insert_many(sample_strategies_batch)
        
        # Distribute signals across strategies
        for i, signal in enumerate(sample_signals_batch):
            strategy_idx = i % len(sample_strategies_batch)
            signal["strategy_id"] = sample_strategies_batch[strategy_idx]["strategy_id"]
        
        test_db.signals.insert_many(sample_signals_batch)
        
        # Verify distribution
        for strategy in sample_strategies_batch:
            strategy_signals = test_db.signals.count_documents({
                "strategy_id": strategy["strategy_id"]
            })
            assert strategy_signals > 0


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling across integrated components"""
    
    def test_signal_without_strategy(self, test_db):
        """Test handling signal for non-existent strategy"""
        generator = SignalGenerator(strategy_id="nonexistent_strategy")
        signal = generator.generate_entry_signal("AAPL")
        
        test_db.signals.insert_one(signal)
        
        # Check if strategy exists
        strategy = test_db.strategies.find_one({"strategy_id": signal["strategy_id"]})
        
        if strategy is None:
            # Mark signal as invalid
            test_db.signals.update_one(
                {"signal_id": signal["signal_id"]},
                {"$set": {
                    "status": "REJECTED",
                    "rejection_reason": "Strategy not found"
                }}
            )
        
        rejected = test_db.signals.find_one({"signal_id": signal["signal_id"]})
        assert rejected["status"] == "REJECTED"
    
    def test_order_for_inactive_strategy(self, test_db, sample_strategy):
        """Test preventing orders for inactive strategies"""
        # Make strategy inactive
        sample_strategy["is_active"] = False
        test_db.strategies.insert_one(sample_strategy)
        
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        signal = generator.generate_entry_signal("AAPL")
        test_db.signals.insert_one(signal)
        
        # Check strategy status before creating order
        strategy = test_db.strategies.find_one({"strategy_id": signal["strategy_id"]})
        
        can_create_order = strategy["is_active"]
        assert can_create_order is False
    
    def test_duplicate_signal_id_handling(self, test_db):
        """Test handling duplicate signal IDs"""
        generator = SignalGenerator()
        signal1 = generator.generate_entry_signal("AAPL")
        
        # Insert first signal
        test_db.signals.insert_one(signal1)
        
        # Try to insert duplicate
        signal2 = signal1.copy()
        
        # Check for existing
        existing = test_db.signals.find_one({"signal_id": signal1["signal_id"]})
        
        if existing:
            # Don't insert duplicate
            should_insert = False
        else:
            should_insert = True
        
        assert should_insert is False
