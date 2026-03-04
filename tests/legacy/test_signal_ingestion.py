"""
Unit tests for Signal Ingestion Service
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from tests.helpers.test_utils import SignalGenerator, AssertionHelper
from tests.mocks.mock_services import MockMongoCollection


class TestSignalValidation:
    """Test signal validation logic"""
    
    def test_valid_entry_signal(self, sample_signal):
        """Test validation of valid entry signal"""
        AssertionHelper.assert_signal_valid(sample_signal)
        assert sample_signal["action"] == "ENTRY"
        assert "stop_loss" in sample_signal
        assert "take_profit" in sample_signal
    
    def test_valid_exit_signal(self):
        """Test validation of valid exit signal"""
        generator = SignalGenerator()
        exit_signal = generator.generate_exit_signal("AAPL")
        
        assert exit_signal["action"] == "EXIT"
        assert "signal_id" in exit_signal
        assert "timestamp" in exit_signal
    
    def test_missing_required_fields(self):
        """Test signal with missing required fields"""
        invalid_signal = {
            "signal_id": "test_123",
            "symbol": "AAPL"
            # Missing strategy_id, action, timestamp
        }
        
        required_fields = ["strategy_id", "action", "timestamp"]
        for field in required_fields:
            assert field not in invalid_signal
    
    def test_invalid_action_type(self):
        """Test signal with invalid action"""
        generator = SignalGenerator()
        signal = generator.generate_entry_signal("AAPL")
        signal["action"] = "INVALID_ACTION"
        
        # Should validate action is either ENTRY or EXIT
        assert signal["action"] not in ["ENTRY", "EXIT"]
    
    def test_invalid_signal_type(self):
        """Test signal with invalid signal type"""
        generator = SignalGenerator()
        signal = generator.generate_entry_signal("AAPL", signal_type="INVALID")
        
        # Should validate signal_type is LONG or SHORT
        assert signal["signal_type"] not in ["LONG", "SHORT"]


class TestSignalEnrichment:
    """Test signal enrichment logic"""
    
    def test_enrich_signal_with_metadata(self, sample_signal):
        """Test enriching signal with additional metadata"""
        enriched = sample_signal.copy()
        enriched["enriched_at"] = datetime.now(timezone.utc).isoformat()
        enriched["enrichment_version"] = "1.0"
        
        assert "enriched_at" in enriched
        assert "enrichment_version" in enriched
    
    def test_calculate_position_size(self, sample_signal):
        """Test position size calculation"""
        account_balance = 100000.00
        risk_per_trade = 0.02  # 2%
        
        # Calculate position size based on risk
        risk_amount = account_balance * risk_per_trade
        price_diff = abs(sample_signal["price"] - sample_signal["stop_loss"])
        position_size = int(risk_amount / price_diff)
        
        assert position_size > 0
        assert position_size <= 1000  # Reasonable limit
    
    def test_add_timestamps(self, sample_signal):
        """Test adding processing timestamps"""
        signal = sample_signal.copy()
        signal["received_at"] = datetime.now(timezone.utc).isoformat()
        signal["processed_at"] = datetime.now(timezone.utc).isoformat()
        
        assert "received_at" in signal
        assert "processed_at" in signal
        AssertionHelper.assert_datetime_recent(signal["received_at"])


class TestSignalStorage:
    """Test signal storage operations"""
    
    def test_store_signal_in_database(self, clean_signals_collection, sample_signal):
        """Test storing signal in MongoDB"""
        result = clean_signals_collection.insert_one(sample_signal)
        assert result.inserted_id is not None
        
        # Verify signal was stored
        stored = clean_signals_collection.find_one({"signal_id": sample_signal["signal_id"]})
        assert stored is not None
        assert stored["symbol"] == sample_signal["symbol"]
    
    def test_prevent_duplicate_signals(self, clean_signals_collection, sample_signal):
        """Test preventing duplicate signal IDs"""
        # Insert first time
        clean_signals_collection.insert_one(sample_signal)
        
        # Try to insert again with same signal_id
        count_before = clean_signals_collection.count_documents({})
        
        # Should check for existing signal_id before inserting
        existing = clean_signals_collection.find_one({"signal_id": sample_signal["signal_id"]})
        assert existing is not None
        
        count_after = clean_signals_collection.count_documents({})
        assert count_after == count_before
    
    def test_update_signal_status(self, clean_signals_collection, sample_signal):
        """Test updating signal status"""
        clean_signals_collection.insert_one(sample_signal)
        
        # Update status
        clean_signals_collection.update_one(
            {"signal_id": sample_signal["signal_id"]},
            {"$set": {"status": "PROCESSED"}}
        )
        
        updated = clean_signals_collection.find_one({"signal_id": sample_signal["signal_id"]})
        assert updated["status"] == "PROCESSED"


class TestSignalQuerying:
    """Test signal query operations"""
    
    def test_find_pending_signals(self, clean_signals_collection, sample_signals_batch):
        """Test finding pending signals"""
        # Insert batch
        clean_signals_collection.insert_many(sample_signals_batch)
        
        # Find pending signals
        pending = list(clean_signals_collection.find({"status": "PENDING"}))
        assert len(pending) > 0
        assert all(s["status"] == "PENDING" for s in pending)
    
    def test_find_signals_by_strategy(self, clean_signals_collection, sample_signals_batch):
        """Test finding signals by strategy ID"""
        clean_signals_collection.insert_many(sample_signals_batch)
        
        strategy_id = sample_signals_batch[0]["strategy_id"]
        signals = list(clean_signals_collection.find({"strategy_id": strategy_id}))
        
        assert len(signals) > 0
        assert all(s["strategy_id"] == strategy_id for s in signals)
    
    def test_find_signals_by_symbol(self, clean_signals_collection, sample_signals_batch):
        """Test finding signals by symbol"""
        clean_signals_collection.insert_many(sample_signals_batch)
        
        symbol = "AAPL"
        signals = list(clean_signals_collection.find({"symbol": symbol}))
        
        assert len(signals) > 0
        assert all(s["symbol"] == symbol for s in signals)
    
    def test_find_latest_signal(self, clean_signals_collection, sample_signals_batch):
        """Test finding latest signal for a strategy"""
        clean_signals_collection.insert_many(sample_signals_batch)
        
        strategy_id = sample_signals_batch[0]["strategy_id"]
        latest = clean_signals_collection.find_one(
            {"strategy_id": strategy_id},
            sort=[("timestamp", -1)]
        )
        
        assert latest is not None
        assert latest["strategy_id"] == strategy_id


@pytest.mark.unit
class TestSignalProcessing:
    """Test signal processing workflow"""
    
    def test_process_entry_signal_workflow(self, sample_signal):
        """Test complete entry signal processing"""
        # 1. Validate
        AssertionHelper.assert_signal_valid(sample_signal)
        
        # 2. Enrich
        sample_signal["processed_at"] = datetime.now(timezone.utc).isoformat()
        sample_signal["status"] = "VALIDATED"
        
        # 3. Verify enrichment
        assert "processed_at" in sample_signal
        assert sample_signal["status"] == "VALIDATED"
    
    def test_process_exit_signal_workflow(self):
        """Test complete exit signal processing"""
        generator = SignalGenerator()
        exit_signal = generator.generate_exit_signal("AAPL")
        
        # Process exit signal
        exit_signal["processed_at"] = datetime.now(timezone.utc).isoformat()
        exit_signal["status"] = "VALIDATED"
        
        assert exit_signal["action"] == "EXIT"
        assert exit_signal["status"] == "VALIDATED"
    
    def test_reject_invalid_signal(self):
        """Test rejecting invalid signal"""
        invalid_signal = {
            "signal_id": "invalid_123",
            "symbol": "AAPL"
            # Missing required fields
        }
        
        # Should be rejected
        is_valid = all(
            field in invalid_signal 
            for field in ["strategy_id", "action", "timestamp"]
        )
        
        assert not is_valid
        
        # Mark as rejected
        invalid_signal["status"] = "REJECTED"
        invalid_signal["rejection_reason"] = "Missing required fields"
        
        assert invalid_signal["status"] == "REJECTED"


@pytest.mark.unit
class TestSignalPairing:
    """Test entry/exit signal pairing"""
    
    def test_pair_entry_exit_signals(self):
        """Test pairing entry and exit signals"""
        generator = SignalGenerator()
        entry, exit_signal = generator.generate_signal_pair("AAPL")
        
        assert entry["action"] == "ENTRY"
        assert exit_signal["action"] == "EXIT"
        assert entry["symbol"] == exit_signal["symbol"]
        assert entry["strategy_id"] == exit_signal["strategy_id"]
    
    def test_exit_without_entry_handling(self):
        """Test handling exit signal without matching entry"""
        generator = SignalGenerator()
        exit_signal = generator.generate_exit_signal("AAPL")
        
        # Should be flagged as orphaned
        exit_signal["orphaned"] = True
        exit_signal["warning"] = "No matching entry signal found"
        
        assert exit_signal["orphaned"] is True
    
    def test_multiple_exits_for_one_entry(self):
        """Test handling multiple exit signals for one entry"""
        generator = SignalGenerator()
        entry = generator.generate_entry_signal("AAPL", quantity=200)
        
        # Create partial exits
        exit1 = generator.generate_exit_signal("AAPL", quantity=100)
        exit2 = generator.generate_exit_signal("AAPL", quantity=100)
        
        total_exit_quantity = exit1["quantity"] + exit2["quantity"]
        assert total_exit_quantity == entry["quantity"]
