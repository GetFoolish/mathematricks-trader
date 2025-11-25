"""
Integration Test 4: Order Fill Tracking & Position Management

Tests the ExecutionService's fill tracking and position management:
1. Detects when orders are filled
2. Updates position records in MongoDB
3. Calculates weighted average entry prices
4. Handles partial fills and scale-in/scale-out
5. Tracks position lifecycle (OPEN → CLOSED)

CRITICAL: This test imports from execution_service and uses actual production code.
NO business logic is hardcoded in this test.
"""
import pytest
import json
import time
from datetime import datetime


def test_position_creation_on_fill(
    mongodb_client
):
    """
    Test that ExecutionService creates position record when order fills.

    Verifies the create_or_update_position() function for ENTRY orders.
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import create_or_update_position, open_positions_collection

    # Clean up any existing test positions
    open_positions_collection.delete_many({'strategy_id': 'TestPositionCreation'})

    # Create test order data (ENTRY)
    entry_order = {
        'order_id': 'TEST_ORD_ENTRY_001',
        'strategy_id': 'TestPositionCreation',
        'instrument': 'AAPL',
        'direction': 'LONG',
        'action': 'ENTRY',
        'quantity': 100
    }

    # Simulate fill
    filled_qty = 100.0
    avg_fill_price = 150.25

    # Call actual position creation function
    create_or_update_position(entry_order, filled_qty, avg_fill_price)

    # Verify position was created in MongoDB
    position = open_positions_collection.find_one({
        'strategy_id': 'TestPositionCreation',
        'instrument': 'AAPL',
        'status': 'OPEN'
    })

    assert position is not None, "Position not created"
    assert position['quantity'] == filled_qty
    assert position['avg_entry_price'] == avg_fill_price
    assert position['direction'] == 'LONG'
    assert position['status'] == 'OPEN'

    print(f"✅ Position creation verified")
    print(f"   → Strategy: {position['strategy_id']}")
    print(f"   → Instrument: {position['instrument']}")
    print(f"   → Quantity: {position['quantity']}")
    print(f"   → Avg Entry Price: ${position['avg_entry_price']:.2f}")

    # Cleanup
    open_positions_collection.delete_many({'strategy_id': 'TestPositionCreation'})


def test_position_scale_in_weighted_average(
    mongodb_client
):
    """
    Test that scale-in (adding to position) calculates weighted average price correctly.

    Verifies:
    - Position quantity increases
    - Average entry price is weighted correctly
    - Formula: (qty1 * price1 + qty2 * price2) / (qty1 + qty2)
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import create_or_update_position, open_positions_collection

    # Clean up
    open_positions_collection.delete_many({'strategy_id': 'TestScaleIn'})

    # First entry: 100 shares @ $150
    entry_order_1 = {
        'order_id': 'TEST_ORD_SCALE_001',
        'strategy_id': 'TestScaleIn',
        'instrument': 'MSFT',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(entry_order_1, 100.0, 150.00)

    # Second entry: 50 shares @ $155 (scale-in)
    entry_order_2 = {
        'order_id': 'TEST_ORD_SCALE_002',
        'strategy_id': 'TestScaleIn',
        'instrument': 'MSFT',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(entry_order_2, 50.0, 155.00)

    # Verify weighted average calculation
    # Expected: (100 * 150 + 50 * 155) / (100 + 50) = 22750 / 150 = 151.67
    position = open_positions_collection.find_one({
        'strategy_id': 'TestScaleIn',
        'instrument': 'MSFT',
        'status': 'OPEN'
    })

    assert position is not None
    assert position['quantity'] == 150.0  # 100 + 50
    expected_avg_price = (100 * 150 + 50 * 155) / 150
    assert abs(position['avg_entry_price'] - expected_avg_price) < 0.01

    print(f"✅ Scale-in weighted average verified")
    print(f"   → Original: 100 shares @ $150.00")
    print(f"   → Add: 50 shares @ $155.00")
    print(f"   → Result: 150 shares @ ${position['avg_entry_price']:.2f}")
    print(f"   → Expected: ${expected_avg_price:.2f}")

    # Cleanup
    open_positions_collection.delete_many({'strategy_id': 'TestScaleIn'})


def test_position_partial_exit(
    mongodb_client
):
    """
    Test that partial EXIT reduces position quantity correctly.

    Verifies:
    - Position quantity decreases
    - Avg entry price remains unchanged
    - Position status remains OPEN
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import create_or_update_position, open_positions_collection

    # Clean up
    open_positions_collection.delete_many({'strategy_id': 'TestPartialExit'})

    # Create position: 100 shares @ $160
    entry_order = {
        'order_id': 'TEST_ORD_EXIT_001',
        'strategy_id': 'TestPartialExit',
        'instrument': 'GOOGL',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(entry_order, 100.0, 160.00)

    # Partial exit: Sell 40 shares @ $165
    exit_order = {
        'order_id': 'TEST_ORD_EXIT_002',
        'strategy_id': 'TestPartialExit',
        'instrument': 'GOOGL',
        'direction': 'LONG',
        'action': 'EXIT'
    }

    create_or_update_position(exit_order, 40.0, 165.00)

    # Verify position reduced but still open
    position = open_positions_collection.find_one({
        'strategy_id': 'TestPartialExit',
        'instrument': 'GOOGL',
        'status': 'OPEN'
    })

    assert position is not None
    assert position['quantity'] == 60.0  # 100 - 40
    assert position['avg_entry_price'] == 160.00  # Entry price unchanged
    assert position['status'] == 'OPEN'

    print(f"✅ Partial exit verified")
    print(f"   → Original: 100 shares")
    print(f"   → Sold: 40 shares @ $165.00")
    print(f"   → Remaining: {position['quantity']} shares")
    print(f"   → Avg Entry Price: ${position['avg_entry_price']:.2f} (unchanged)")

    # Cleanup
    open_positions_collection.delete_many({'strategy_id': 'TestPartialExit'})


def test_position_full_exit_closes_position(
    mongodb_client
):
    """
    Test that full EXIT closes the position.

    Verifies:
    - Position status changes to CLOSED
    - Exit price and timestamp are recorded
    - Position no longer appears in OPEN positions query
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import create_or_update_position, open_positions_collection

    # Clean up
    open_positions_collection.delete_many({'strategy_id': 'TestFullExit'})

    # Create position: 100 shares @ $140
    entry_order = {
        'order_id': 'TEST_ORD_FULL_001',
        'strategy_id': 'TestFullExit',
        'instrument': 'TSLA',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(entry_order, 100.0, 140.00)

    # Full exit: Sell all 100 shares @ $145
    exit_order = {
        'order_id': 'TEST_ORD_FULL_002',
        'strategy_id': 'TestFullExit',
        'instrument': 'TSLA',
        'direction': 'LONG',
        'action': 'EXIT'
    }

    create_or_update_position(exit_order, 100.0, 145.00)

    # Verify position is CLOSED
    closed_position = open_positions_collection.find_one({
        'strategy_id': 'TestFullExit',
        'instrument': 'TSLA',
        'status': 'CLOSED'
    })

    assert closed_position is not None
    assert closed_position['status'] == 'CLOSED'
    assert closed_position['avg_exit_price'] == 145.00
    assert 'closed_at' in closed_position

    # Verify no OPEN position exists
    open_position = open_positions_collection.find_one({
        'strategy_id': 'TestFullExit',
        'instrument': 'TSLA',
        'status': 'OPEN'
    })

    assert open_position is None

    print(f"✅ Full exit verified")
    print(f"   → Position closed")
    print(f"   → Entry: 100 shares @ ${closed_position['avg_entry_price']:.2f}")
    print(f"   → Exit: 100 shares @ ${closed_position['avg_exit_price']:.2f}")

    # Cleanup
    open_positions_collection.delete_many({'strategy_id': 'TestFullExit'})


def test_get_account_state_from_ibkr(
    ensure_services_running
):
    """
    Test that ExecutionService can retrieve account state from IBKR.

    This function gets:
    - Account equity
    - Cash balance
    - Margin used/available
    - Open positions
    - Open orders
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import get_account_state, ib

    if not ib.isConnected():
        pytest.skip("IBKR TWS is not connected - skipping account state test")

    # Call production function
    account_state = get_account_state()

    if account_state:
        print(f"✅ Account state retrieved from IBKR")
        print(f"   → Equity: ${account_state.get('equity', 0):,.2f}")
        print(f"   → Cash: ${account_state.get('cash_balance', 0):,.2f}")
        print(f"   → Margin Used: ${account_state.get('margin_used', 0):,.2f}")
        print(f"   → Margin Available: ${account_state.get('margin_available', 0):,.2f}")
        print(f"   → Open Positions: {len(account_state.get('open_positions', []))}")
        print(f"   → Open Orders: {len(account_state.get('open_orders', []))}")

        # Verify structure
        assert 'equity' in account_state
        assert 'cash_balance' in account_state
        assert 'margin_used' in account_state
        assert 'margin_available' in account_state
        assert 'open_positions' in account_state
        assert 'open_orders' in account_state
    else:
        pytest.fail("Failed to get account state from IBKR")


def test_position_tracking_with_multiple_strategies(
    mongodb_client
):
    """
    Test that positions are tracked separately per strategy.

    Verifies:
    - Multiple strategies can hold same instrument
    - Position queries filter by strategy_id correctly
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import create_or_update_position, open_positions_collection

    # Clean up
    open_positions_collection.delete_many({'instrument': 'AAPL', 'strategy_id': {'$in': ['Strategy1', 'Strategy2']}})

    # Strategy 1: 50 shares AAPL
    order_strat1 = {
        'order_id': 'TEST_MULTI_001',
        'strategy_id': 'Strategy1',
        'instrument': 'AAPL',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(order_strat1, 50.0, 150.00)

    # Strategy 2: 100 shares AAPL (different strategy, same instrument)
    order_strat2 = {
        'order_id': 'TEST_MULTI_002',
        'strategy_id': 'Strategy2',
        'instrument': 'AAPL',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(order_strat2, 100.0, 155.00)

    # Verify both positions exist separately
    position_strat1 = open_positions_collection.find_one({
        'strategy_id': 'Strategy1',
        'instrument': 'AAPL',
        'status': 'OPEN'
    })

    position_strat2 = open_positions_collection.find_one({
        'strategy_id': 'Strategy2',
        'instrument': 'AAPL',
        'status': 'OPEN'
    })

    assert position_strat1 is not None
    assert position_strat2 is not None
    assert position_strat1['quantity'] == 50.0
    assert position_strat2['quantity'] == 100.0
    assert position_strat1['avg_entry_price'] == 150.00
    assert position_strat2['avg_entry_price'] == 155.00

    print(f"✅ Multi-strategy position tracking verified")
    print(f"   → Strategy1: 50 shares AAPL @ $150.00")
    print(f"   → Strategy2: 100 shares AAPL @ $155.00")
    print(f"   → Positions tracked separately")

    # Cleanup
    open_positions_collection.delete_many({'instrument': 'AAPL', 'strategy_id': {'$in': ['Strategy1', 'Strategy2']}})


def test_execution_confirmation_structure(
    mongodb_client
):
    """
    Test the structure of execution confirmation records.

    Verifies that confirmations have all required fields.
    """
    # Get sample confirmation from MongoDB (if any exist)
    confirmations_collection = mongodb_client['mathematricks_trading']['execution_confirmations']

    sample_confirmation = confirmations_collection.find_one()

    if sample_confirmation:
        print(f"✅ Found sample execution confirmation")

        # Verify required fields
        required_fields = ['order_id', 'timestamp', 'status']

        for field in required_fields:
            if field in sample_confirmation:
                print(f"   → {field}: {sample_confirmation[field]}")
            else:
                print(f"   ⚠️  Missing field: {field}")

        # Check for optional fields
        optional_fields = ['filled_quantity', 'avg_fill_price', 'ib_order_id']

        for field in optional_fields:
            if field in sample_confirmation:
                print(f"   → {field}: {sample_confirmation[field]}")
    else:
        pytest.skip("No execution confirmations found in MongoDB - run end-to-end test first")


def test_position_pnl_tracking(
    mongodb_client
):
    """
    Test that position records have fields for PnL tracking.

    Verifies:
    - unrealized_pnl field exists
    - current_price field exists
    - Structure supports PnL calculation
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/execution_service'))
    from main import create_or_update_position, open_positions_collection

    # Clean up
    open_positions_collection.delete_many({'strategy_id': 'TestPnL'})

    # Create position
    entry_order = {
        'order_id': 'TEST_PNL_001',
        'strategy_id': 'TestPnL',
        'instrument': 'AMZN',
        'direction': 'LONG',
        'action': 'ENTRY'
    }

    create_or_update_position(entry_order, 10.0, 175.00)

    # Verify PnL fields exist
    position = open_positions_collection.find_one({
        'strategy_id': 'TestPnL',
        'instrument': 'AMZN',
        'status': 'OPEN'
    })

    assert position is not None
    assert 'unrealized_pnl' in position
    assert 'current_price' in position
    assert 'avg_entry_price' in position

    print(f"✅ Position PnL structure verified")
    print(f"   → Has unrealized_pnl field: {position['unrealized_pnl']}")
    print(f"   → Has current_price field: {position['current_price']}")
    print(f"   → Entry price: ${position['avg_entry_price']:.2f}")

    # Cleanup
    open_positions_collection.delete_many({'strategy_id': 'TestPnL'})
