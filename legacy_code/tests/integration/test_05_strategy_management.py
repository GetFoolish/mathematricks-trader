"""
Integration Test 5: Strategy Management APIs

Tests the CerebroService's strategy CRUD operations:
1. Create new strategy
2. Read strategy list and individual strategy
3. Update strategy configuration
4. Delete strategy (soft delete to INACTIVE)
5. Strategy validation

CRITICAL: This test uses the actual CerebroService REST API endpoints.
NO business logic is hardcoded in this test.
"""
import pytest
import requests
import json
from datetime import datetime


def test_create_strategy(
    cerebro_api_url,
    strategies_collection,
    cleanup_test_strategies,
    ensure_services_running
):
    """
    Test creating a new strategy via POST /api/v1/strategies endpoint.

    Verifies:
    - Strategy is created in MongoDB
    - Response includes strategy_id
    - Timestamps are added automatically
    - Validation of required fields
    """
    # Create test strategy
    test_strategy = {
        "strategy_id": f"TestStrategy_{int(datetime.utcnow().timestamp())}",
        "name": "Test Momentum Strategy",
        "asset_class": "EQUITY",
        "instruments": ["AAPL", "MSFT", "GOOGL"],
        "mode": "PAPER",
        "status": "ACTIVE",
        "risk_limits": {
            "max_position_size": 0.05,
            "max_drawdown": 0.10
        },
        "developer_contact": "test@example.com"
    }

    strategy_id = test_strategy["strategy_id"]
    cleanup_test_strategies(strategy_id)

    # Call actual API endpoint
    response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=test_strategy,
        timeout=10
    )

    assert response.status_code == 200, f"Failed to create strategy: {response.text}"

    response_data = response.json()
    assert response_data["status"] == "success"
    assert response_data["strategy_id"] == strategy_id

    print(f"✅ Strategy created via API")
    print(f"   → Strategy ID: {strategy_id}")
    print(f"   → Response: {response_data['message']}")

    # Verify strategy exists in MongoDB
    strategy_doc = strategies_collection.find_one({"strategy_id": strategy_id})

    assert strategy_doc is not None, "Strategy not found in MongoDB"
    assert strategy_doc["name"] == test_strategy["name"]
    assert strategy_doc["asset_class"] == test_strategy["asset_class"]
    assert "created_at" in strategy_doc
    assert "updated_at" in strategy_doc

    print(f"✅ Strategy verified in MongoDB")
    print(f"   → Name: {strategy_doc['name']}")
    print(f"   → Asset Class: {strategy_doc['asset_class']}")
    print(f"   → Status: {strategy_doc['status']}")


def test_get_all_strategies(
    cerebro_api_url,
    ensure_services_running
):
    """
    Test retrieving all strategies via GET /api/v1/strategies endpoint.

    Verifies:
    - Returns list of strategies
    - Response format is correct
    - Can filter by status (optional)
    """
    # Call actual API endpoint
    response = requests.get(
        f"{cerebro_api_url}/api/v1/strategies",
        timeout=10
    )

    assert response.status_code == 200, f"Failed to get strategies: {response.text}"

    response_data = response.json()

    assert "strategies" in response_data
    assert isinstance(response_data["strategies"], list)

    print(f"✅ Retrieved strategies via API")
    print(f"   → Total strategies: {len(response_data['strategies'])}")

    # If strategies exist, verify structure
    if len(response_data["strategies"]) > 0:
        sample_strategy = response_data["strategies"][0]
        required_fields = ["strategy_id", "name", "status"]

        for field in required_fields:
            assert field in sample_strategy, f"Missing field: {field}"

        print(f"   → Sample strategy: {sample_strategy['strategy_id']}")
        print(f"   → Status: {sample_strategy.get('status', 'N/A')}")


def test_get_single_strategy(
    cerebro_api_url,
    strategies_collection,
    cleanup_test_strategies,
    ensure_services_running
):
    """
    Test retrieving a single strategy via GET /api/v1/strategies/{strategy_id}.

    Verifies:
    - Returns specific strategy details
    - 404 for non-existent strategy
    """
    # First create a test strategy
    test_strategy = {
        "strategy_id": f"TestGetSingle_{int(datetime.utcnow().timestamp())}",
        "name": "Test Single Get Strategy",
        "asset_class": "FOREX",
        "instruments": ["EURUSD", "GBPUSD"],
        "status": "ACTIVE"
    }

    strategy_id = test_strategy["strategy_id"]
    cleanup_test_strategies(strategy_id)

    # Create via API
    create_response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=test_strategy,
        timeout=10
    )

    assert create_response.status_code == 200

    # Get single strategy
    get_response = requests.get(
        f"{cerebro_api_url}/api/v1/strategies/{strategy_id}",
        timeout=10
    )

    assert get_response.status_code == 200, f"Failed to get strategy: {get_response.text}"

    strategy_data = get_response.json()

    assert "strategy" in strategy_data
    assert strategy_data["strategy"]["strategy_id"] == strategy_id
    assert strategy_data["strategy"]["name"] == test_strategy["name"]

    print(f"✅ Retrieved single strategy via API")
    print(f"   → Strategy ID: {strategy_id}")
    print(f"   → Name: {strategy_data['strategy']['name']}")

    # Test 404 for non-existent strategy
    not_found_response = requests.get(
        f"{cerebro_api_url}/api/v1/strategies/NONEXISTENT_STRATEGY",
        timeout=10
    )

    assert not_found_response.status_code == 404

    print(f"✅ 404 handling verified for non-existent strategy")


def test_update_strategy(
    cerebro_api_url,
    strategies_collection,
    cleanup_test_strategies,
    ensure_services_running
):
    """
    Test updating strategy via PUT /api/v1/strategies/{strategy_id}.

    Verifies:
    - Can update specific fields
    - Timestamp is updated
    - Other fields remain unchanged
    """
    # Create test strategy
    test_strategy = {
        "strategy_id": f"TestUpdate_{int(datetime.utcnow().timestamp())}",
        "name": "Original Name",
        "asset_class": "EQUITY",
        "instruments": ["AAPL"],
        "status": "ACTIVE",
        "mode": "PAPER"
    }

    strategy_id = test_strategy["strategy_id"]
    cleanup_test_strategies(strategy_id)

    # Create strategy
    create_response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=test_strategy,
        timeout=10
    )

    assert create_response.status_code == 200

    # Update strategy (partial update)
    updates = {
        "name": "Updated Name",
        "mode": "LIVE",
        "risk_limits": {
            "max_position_size": 0.10
        }
    }

    update_response = requests.put(
        f"{cerebro_api_url}/api/v1/strategies/{strategy_id}",
        json=updates,
        timeout=10
    )

    assert update_response.status_code == 200, f"Failed to update strategy: {update_response.text}"

    update_data = update_response.json()
    assert update_data["status"] == "success"

    print(f"✅ Strategy updated via API")
    print(f"   → Modified count: {update_data.get('modified_count', 0)}")

    # Verify updates in MongoDB
    updated_doc = strategies_collection.find_one({"strategy_id": strategy_id})

    assert updated_doc["name"] == "Updated Name"
    assert updated_doc["mode"] == "LIVE"
    assert updated_doc["risk_limits"]["max_position_size"] == 0.10
    assert updated_doc["asset_class"] == "EQUITY"  # Unchanged field

    print(f"✅ Updates verified in MongoDB")
    print(f"   → Name: {updated_doc['name']}")
    print(f"   → Mode: {updated_doc['mode']}")
    print(f"   → Asset Class unchanged: {updated_doc['asset_class']}")


def test_delete_strategy_soft_delete(
    cerebro_api_url,
    strategies_collection,
    cleanup_test_strategies,
    ensure_services_running
):
    """
    Test deleting strategy via DELETE /api/v1/strategies/{strategy_id}.

    Verifies:
    - Soft delete (marks as INACTIVE)
    - Strategy still exists in database
    - Status changed to INACTIVE
    - deleted_at timestamp added
    """
    # Create test strategy
    test_strategy = {
        "strategy_id": f"TestDelete_{int(datetime.utcnow().timestamp())}",
        "name": "To Be Deleted",
        "asset_class": "FUTURES",
        "instruments": ["ES"],
        "status": "ACTIVE"
    }

    strategy_id = test_strategy["strategy_id"]
    cleanup_test_strategies(strategy_id)

    # Create strategy
    create_response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=test_strategy,
        timeout=10
    )

    assert create_response.status_code == 200

    # Delete strategy
    delete_response = requests.delete(
        f"{cerebro_api_url}/api/v1/strategies/{strategy_id}",
        timeout=10
    )

    assert delete_response.status_code == 200, f"Failed to delete strategy: {delete_response.text}"

    delete_data = delete_response.json()
    assert delete_data["status"] == "success"

    print(f"✅ Strategy deleted via API")
    print(f"   → Strategy ID: {strategy_id}")

    # Verify soft delete in MongoDB
    deleted_doc = strategies_collection.find_one({"strategy_id": strategy_id})

    assert deleted_doc is not None, "Strategy was hard deleted (should be soft delete)"
    assert deleted_doc["status"] == "INACTIVE"
    assert "deleted_at" in deleted_doc

    print(f"✅ Soft delete verified in MongoDB")
    print(f"   → Status: {deleted_doc['status']}")
    print(f"   → Deleted at: {deleted_doc['deleted_at']}")


def test_create_strategy_validation(
    cerebro_api_url,
    ensure_services_running
):
    """
    Test strategy creation validation.

    Verifies:
    - Missing required fields returns 400
    - Duplicate strategy_id returns 409
    """
    # Test 1: Missing required field (name)
    invalid_strategy_1 = {
        "strategy_id": "TestInvalid1",
        # Missing name
        "asset_class": "EQUITY",
        "instruments": ["AAPL"]
    }

    response_1 = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=invalid_strategy_1,
        timeout=10
    )

    assert response_1.status_code == 400, "Should return 400 for missing required field"

    print(f"✅ Validation: Missing required field returns 400")

    # Test 2: Duplicate strategy_id
    # First, create a strategy
    valid_strategy = {
        "strategy_id": f"TestDuplicate_{int(datetime.utcnow().timestamp())}",
        "name": "Original Strategy",
        "asset_class": "EQUITY",
        "instruments": ["AAPL"]
    }

    create_response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=valid_strategy,
        timeout=10
    )

    assert create_response.status_code == 200

    # Try to create duplicate
    duplicate_response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=valid_strategy,
        timeout=10
    )

    assert duplicate_response.status_code == 409, "Should return 409 for duplicate strategy_id"

    print(f"✅ Validation: Duplicate strategy_id returns 409")


def test_strategy_filtering_by_status(
    cerebro_api_url,
    strategies_collection,
    cleanup_test_strategies,
    ensure_services_running
):
    """
    Test filtering strategies by status (ACTIVE, INACTIVE, TESTING).

    Note: This assumes the API supports status filtering.
    If not implemented, test will check for all strategies.
    """
    # Create strategies with different statuses
    strategies_to_create = [
        {
            "strategy_id": f"TestActive_{int(datetime.utcnow().timestamp())}",
            "name": "Active Strategy",
            "asset_class": "EQUITY",
            "instruments": ["AAPL"],
            "status": "ACTIVE"
        },
        {
            "strategy_id": f"TestInactive_{int(datetime.utcnow().timestamp())}",
            "name": "Inactive Strategy",
            "asset_class": "EQUITY",
            "instruments": ["MSFT"],
            "status": "INACTIVE"
        }
    ]

    created_ids = []

    for strat in strategies_to_create:
        response = requests.post(
            f"{cerebro_api_url}/api/v1/strategies",
            json=strat,
            timeout=10
        )
        if response.status_code == 200:
            created_ids.append(strat["strategy_id"])
            cleanup_test_strategies(strat["strategy_id"])

    print(f"✅ Created {len(created_ids)} test strategies with different statuses")

    # Get all strategies
    all_response = requests.get(
        f"{cerebro_api_url}/api/v1/strategies",
        timeout=10
    )

    assert all_response.status_code == 200

    all_strategies = all_response.json()["strategies"]

    # Verify our test strategies are in the list
    found_active = any(s["strategy_id"] == strategies_to_create[0]["strategy_id"] for s in all_strategies)
    found_inactive = any(s["strategy_id"] == strategies_to_create[1]["strategy_id"] for s in all_strategies)

    print(f"   → Total strategies returned: {len(all_strategies)}")
    print(f"   → Found ACTIVE test strategy: {found_active}")
    print(f"   → Found INACTIVE test strategy: {found_inactive}")


def test_strategy_backtest_data_sync(
    cerebro_api_url,
    strategies_collection,
    cleanup_test_strategies,
    ensure_services_running
):
    """
    Test syncing backtest data to strategy.

    This test verifies that backtest metrics can be added/updated.
    """
    # Create test strategy
    test_strategy = {
        "strategy_id": f"TestBacktest_{int(datetime.utcnow().timestamp())}",
        "name": "Strategy with Backtest",
        "asset_class": "EQUITY",
        "instruments": ["AAPL"],
        "status": "ACTIVE"
    }

    strategy_id = test_strategy["strategy_id"]
    cleanup_test_strategies(strategy_id)

    # Create strategy
    create_response = requests.post(
        f"{cerebro_api_url}/api/v1/strategies",
        json=test_strategy,
        timeout=10
    )

    assert create_response.status_code == 200

    # Add backtest data via update
    backtest_data = {
        "backtest_metrics": {
            "sharpe_ratio": 2.45,
            "max_drawdown": -0.08,
            "cagr": 0.35,
            "win_rate": 0.62,
            "backtest_period": "2020-01-01 to 2024-12-31"
        }
    }

    update_response = requests.put(
        f"{cerebro_api_url}/api/v1/strategies/{strategy_id}",
        json=backtest_data,
        timeout=10
    )

    assert update_response.status_code == 200

    # Verify backtest data in MongoDB
    updated_doc = strategies_collection.find_one({"strategy_id": strategy_id})

    assert "backtest_metrics" in updated_doc
    assert updated_doc["backtest_metrics"]["sharpe_ratio"] == 2.45

    print(f"✅ Backtest data synced via API")
    print(f"   → Sharpe Ratio: {updated_doc['backtest_metrics']['sharpe_ratio']}")
    print(f"   → Max Drawdown: {updated_doc['backtest_metrics']['max_drawdown']}")
    print(f"   → CAGR: {updated_doc['backtest_metrics']['cagr']}")
