"""
End-to-end test scenarios
Tests complete user workflows from signal submission to position management
"""

import pytest
from datetime import datetime, timezone
import time

from tests.helpers.test_utils import SignalGenerator, TestDataGenerator
from tests.helpers.db_helpers import DatabaseTestHelper


@pytest.mark.e2e
@pytest.mark.docker
class TestCompleteTradeLifecycle:
    """Test complete trade lifecycle end-to-end"""
    
    def test_full_long_trade_lifecycle(
        self,
        test_db,
        sample_strategy,
        sample_account,
        mock_ibkr_gateway
    ):
        """Test complete long trade: signal -> entry -> hold -> exit"""
        db_helper = DatabaseTestHelper(test_db)
        
        # SETUP
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # STEP 1: Entry Signal
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        entry_signal = generator.generate_entry_signal(
            symbol="AAPL",
            signal_type="LONG",
            price=150.00,
            quantity=100
        )
        test_db.signals.insert_one(entry_signal)
        
        # Verify signal stored
        db_helper.assert_signal_exists(entry_signal["signal_id"])
        
        # STEP 2: Process Entry Signal
        test_db.signals.update_one(
            {"signal_id": entry_signal["signal_id"]},
            {"$set": {"status": "PROCESSING"}}
        )
        
        # STEP 3: Place Buy Order
        buy_order = mock_ibkr_gateway.place_order(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="MARKET"
        )
        
        order_doc = {
            "order_id": buy_order["order_id"],
            "signal_id": entry_signal["signal_id"],
            "strategy_id": sample_strategy["strategy_id"],
            "account_id": sample_account["account_id"],
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MARKET",
            "status": "SUBMITTED",
            "submitted_time": datetime.now(timezone.utc).isoformat()
        }
        test_db.orders.insert_one(order_doc)
        
        # STEP 4: Order Fills
        mock_ibkr_gateway.fill_order(buy_order["order_id"], 150.05)
        
        test_db.orders.update_one(
            {"order_id": buy_order["order_id"]},
            {"$set": {
                "status": "FILLED",
                "filled_quantity": 100,
                "avg_fill_price": 150.05,
                "filled_time": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # STEP 5: Create Position
        position = {
            "position_id": f"pos_{int(datetime.now().timestamp())}",
            "signal_id": entry_signal["signal_id"],
            "order_id": buy_order["order_id"],
            "strategy_id": sample_strategy["strategy_id"],
            "account_id": sample_account["account_id"],
            "symbol": "AAPL",
            "position_type": "LONG",
            "quantity": 100,
            "entry_price": 150.05,
            "current_price": 150.05,
            "stop_loss": 145.00,
            "take_profit": 160.00,
            "status": "OPEN",
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "pnl": 0.00,
            "pnl_percent": 0.00
        }
        test_db.positions.insert_one(position)
        
        # Verify position created
        db_helper.assert_position_exists(position["position_id"])
        
        # STEP 6: Price Movement (simulate time passing)
        test_db.positions.update_one(
            {"position_id": position["position_id"]},
            {"$set": {
                "current_price": 155.00,
                "pnl": (155.00 - 150.05) * 100,
                "pnl_percent": ((155.00 - 150.05) / 150.05) * 100
            }}
        )
        
        # STEP 7: Exit Signal
        exit_signal = generator.generate_exit_signal(
            symbol="AAPL",
            signal_type="LONG",
            price=155.00,
            quantity=100,
            reason="take_profit"
        )
        test_db.signals.insert_one(exit_signal)
        
        # STEP 8: Place Sell Order
        sell_order = mock_ibkr_gateway.place_order(
            symbol="AAPL",
            action="SELL",
            quantity=100,
            order_type="MARKET"
        )
        
        sell_order_doc = {
            "order_id": sell_order["order_id"],
            "signal_id": exit_signal["signal_id"],
            "strategy_id": sample_strategy["strategy_id"],
            "account_id": sample_account["account_id"],
            "symbol": "AAPL",
            "action": "SELL",
            "quantity": 100,
            "order_type": "MARKET",
            "status": "SUBMITTED",
            "submitted_time": datetime.now(timezone.utc).isoformat()
        }
        test_db.orders.insert_one(sell_order_doc)
        
        # STEP 9: Sell Order Fills
        mock_ibkr_gateway.fill_order(sell_order["order_id"], 154.95)
        
        test_db.orders.update_one(
            {"order_id": sell_order["order_id"]},
            {"$set": {
                "status": "FILLED",
                "filled_quantity": 100,
                "avg_fill_price": 154.95,
                "filled_time": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # STEP 10: Close Position
        realized_pnl = (154.95 - 150.05) * 100
        
        test_db.positions.update_one(
            {"position_id": position["position_id"]},
            {"$set": {
                "status": "CLOSED",
                "exit_price": 154.95,
                "exit_time": datetime.now(timezone.utc).isoformat(),
                "realized_pnl": realized_pnl,
                "exit_order_id": sell_order["order_id"]
            }}
        )
        
        # VERIFY FINAL STATE
        final_position = test_db.positions.find_one({"position_id": position["position_id"]})
        assert final_position["status"] == "CLOSED"
        assert final_position["realized_pnl"] == 490.00  # (154.95 - 150.05) * 100
        
        entry_order = test_db.orders.find_one({"signal_id": entry_signal["signal_id"]})
        exit_order = test_db.orders.find_one({"signal_id": exit_signal["signal_id"]})
        
        assert entry_order["status"] == "FILLED"
        assert exit_order["status"] == "FILLED"


@pytest.mark.e2e
class TestMultiplePositionsScenario:
    """Test managing multiple positions simultaneously"""
    
    def test_multiple_open_positions(
        self,
        test_db,
        sample_strategy,
        sample_account,
        mock_ibkr_gateway
    ):
        """Test opening multiple positions across different symbols"""
        db_helper = DatabaseTestHelper(test_db)
        
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        symbols = ["AAPL", "GOOGL", "MSFT"]
        positions = []
        
        for symbol in symbols:
            # Create entry signal
            generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
            signal = generator.generate_entry_signal(symbol, price=150.00, quantity=100)
            test_db.signals.insert_one(signal)
            
            # Place order
            order = mock_ibkr_gateway.place_order(symbol, "BUY", 100)
            mock_ibkr_gateway.fill_order(order["order_id"], 150.05)
            
            # Create position
            position = {
                "position_id": f"pos_{symbol}_{int(datetime.now().timestamp())}",
                "signal_id": signal["signal_id"],
                "strategy_id": sample_strategy["strategy_id"],
                "symbol": symbol,
                "quantity": 100,
                "entry_price": 150.05,
                "status": "OPEN"
            }
            test_db.positions.insert_one(position)
            positions.append(position)
        
        # Verify all positions are open
        open_positions = list(test_db.positions.find({"status": "OPEN"}))
        assert len(open_positions) == 3
        
        # Verify each symbol has a position
        position_symbols = {p["symbol"] for p in open_positions}
        assert position_symbols == set(symbols)


@pytest.mark.e2e
class TestStopLossScenario:
    """Test stop loss execution scenarios"""
    
    def test_stop_loss_triggered(
        self,
        test_db,
        sample_strategy,
        sample_account,
        mock_ibkr_gateway
    ):
        """Test position closed by stop loss"""
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # Open position
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        entry_signal = generator.generate_entry_signal(
            symbol="AAPL",
            price=150.00,
            quantity=100
        )
        entry_signal["stop_loss"] = 145.00
        test_db.signals.insert_one(entry_signal)
        
        # Fill entry order
        buy_order = mock_ibkr_gateway.place_order("AAPL", "BUY", 100)
        mock_ibkr_gateway.fill_order(buy_order["order_id"], 150.00)
        
        position = {
            "position_id": f"pos_{int(datetime.now().timestamp())}",
            "signal_id": entry_signal["signal_id"],
            "strategy_id": sample_strategy["strategy_id"],
            "symbol": "AAPL",
            "quantity": 100,
            "entry_price": 150.00,
            "stop_loss": 145.00,
            "status": "OPEN"
        }
        test_db.positions.insert_one(position)
        
        # Simulate price dropping to stop loss
        exit_signal = generator.generate_exit_signal(
            symbol="AAPL",
            price=145.00,
            quantity=100,
            reason="stop_loss"
        )
        test_db.signals.insert_one(exit_signal)
        
        # Execute stop loss
        sell_order = mock_ibkr_gateway.place_order("AAPL", "SELL", 100)
        mock_ibkr_gateway.fill_order(sell_order["order_id"], 145.00)
        
        # Close position with loss
        loss = (145.00 - 150.00) * 100
        test_db.positions.update_one(
            {"position_id": position["position_id"]},
            {"$set": {
                "status": "CLOSED",
                "exit_price": 145.00,
                "realized_pnl": loss,
                "exit_reason": "stop_loss"
            }}
        )
        
        # Verify
        closed_position = test_db.positions.find_one({"position_id": position["position_id"]})
        assert closed_position["status"] == "CLOSED"
        assert closed_position["realized_pnl"] == -500.00
        assert closed_position["exit_reason"] == "stop_loss"


@pytest.mark.e2e
class TestStrategyManagement:
    """Test strategy lifecycle management"""
    
    def test_deactivate_strategy_stops_trading(
        self,
        test_db,
        sample_strategy
    ):
        """Test that deactivating strategy prevents new trades"""
        # Setup active strategy
        sample_strategy["is_active"] = True
        test_db.strategies.insert_one(sample_strategy)
        
        # Create signal while active
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        signal1 = generator.generate_entry_signal("AAPL")
        test_db.signals.insert_one(signal1)
        
        # Deactivate strategy
        test_db.strategies.update_one(
            {"strategy_id": sample_strategy["strategy_id"]},
            {"$set": {"is_active": False}}
        )
        
        # Try to create new signal
        signal2 = generator.generate_entry_signal("GOOGL")
        test_db.signals.insert_one(signal2)
        
        # Check if strategy is active before processing
        strategy = test_db.strategies.find_one({"strategy_id": sample_strategy["strategy_id"]})
        
        if not strategy["is_active"]:
            # Mark signal as rejected
            test_db.signals.update_one(
                {"signal_id": signal2["signal_id"]},
                {"$set": {
                    "status": "REJECTED",
                    "rejection_reason": "Strategy is inactive"
                }}
            )
        
        # Verify
        rejected = test_db.signals.find_one({"signal_id": signal2["signal_id"]})
        assert rejected["status"] == "REJECTED"


@pytest.mark.e2e
@pytest.mark.slow
class TestHighVolumeScenario:
    """Test system under high volume"""
    
    def test_process_100_signals(
        self,
        test_db,
        sample_strategy,
        sample_account
    ):
        """Test processing large number of signals"""
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # Generate 100 signals
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        signals = []
        
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        
        for i in range(100):
            symbol = symbols[i % len(symbols)]
            signal = generator.generate_entry_signal(symbol)
            signals.append(signal)
        
        # Insert in batch
        start_time = time.time()
        test_db.signals.insert_many(signals)
        insert_time = time.time() - start_time
        
        # Verify all inserted
        count = test_db.signals.count_documents({
            "strategy_id": sample_strategy["strategy_id"]
        })
        
        assert count == 100
        assert insert_time < 5.0  # Should complete in reasonable time


@pytest.mark.e2e
class TestErrorRecovery:
    """Test error recovery scenarios"""
    
    def test_recover_from_failed_order(
        self,
        test_db,
        sample_strategy,
        sample_account,
        broker_error_responses
    ):
        """Test recovery from failed order submission"""
        # Setup
        test_db.strategies.insert_one(sample_strategy)
        test_db.trading_accounts.insert_one(sample_account)
        
        # Create signal
        generator = SignalGenerator(strategy_id=sample_strategy["strategy_id"])
        signal = generator.generate_entry_signal("AAPL")
        test_db.signals.insert_one(signal)
        
        # Simulate order failure
        failed_order = {
            "order_id": f"ord_{int(datetime.now().timestamp())}",
            "signal_id": signal["signal_id"],
            "strategy_id": sample_strategy["strategy_id"],
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "status": "REJECTED",
            "rejection_reason": broker_error_responses["order_rejected"]["message"],
            "submitted_time": datetime.now(timezone.utc).isoformat()
        }
        test_db.orders.insert_one(failed_order)
        
        # Update signal status
        test_db.signals.update_one(
            {"signal_id": signal["signal_id"]},
            {"$set": {
                "status": "FAILED",
                "error": failed_order["rejection_reason"]
            }}
        )
        
        # Verify error recorded
        failed_signal = test_db.signals.find_one({"signal_id": signal["signal_id"]})
        assert failed_signal["status"] == "FAILED"
        assert "error" in failed_signal
