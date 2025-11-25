"""
Integration Test 1: Signal Ingestion Pipeline

Tests the complete signal ingestion flow:
1. Signal sent to TradingView webhook (MongoDB)
2. signal_collector.py picks up signal from MongoDB
3. signal_collector.py publishes to Pub/Sub 'standardized-signals' topic

CRITICAL: This test imports from signal_collector.py and uses actual production code.
NO business logic is hardcoded in this test.
"""
import pytest
import json
import time
import subprocess
import os
from datetime import datetime


def test_signal_ingestion_from_script_to_pubsub(
    test_signal_factory,
    signals_collection,
    cleanup_test_signals,
    pubsub_subscriber,
    pubsub_project_id,
    wait_for_mongodb_document,
    wait_for_pubsub_message,
    ensure_services_running
):
    """
    Test full signal ingestion pipeline using send_test_FOREX_signal.sh script.

    Flow:
    1. Run send_test_FOREX_signal.sh → sends signal to staging.mathematricks.fund
    2. Signal gets stored in MongoDB by Vercel webhook
    3. signal_collector.py (running via run_mvp_demo.sh) picks up signal
    4. signal_collector.py publishes standardized signal to Pub/Sub
    5. Test verifies signal appears in Pub/Sub subscription
    """

    # Step 1: Send test signal using the actual script
    script_path = os.path.join(
        os.path.dirname(__file__),
        '../../dev/leslie_strategies/send_test_FOREX_signal.sh'
    )

    # Make script executable
    os.chmod(script_path, 0o755)

    # Run the signal sender script
    result = subprocess.run(
        [script_path],
        capture_output=True,
        text=True,
        timeout=10
    )

    # Verify script ran successfully
    assert result.returncode == 0, f"Signal sender script failed: {result.stderr}"
    print(f"✅ Signal sent via script")

    # Step 2: Wait for signal to appear in MongoDB
    # The signal_collector.py watches MongoDB, so we verify it's there first
    query = {
        'strategy_name': 'Forex',
        'signal.ticker': 'AUDNZD',
        'environment': 'staging'
    }

    signal_doc = wait_for_mongodb_document(
        signals_collection,
        query,
        timeout=10
    )

    assert signal_doc is not None, "Signal not found in MongoDB after 10 seconds"
    print(f"✅ Signal found in MongoDB: {signal_doc.get('signalID')}")

    # Register for cleanup
    cleanup_test_signals(signal_doc.get('signalID'))

    # Step 3: Wait for signal to be published to Pub/Sub by signal_collector.py
    # The signal_collector.py should pick up the signal and publish it
    subscription_path = pubsub_subscriber.subscription_path(
        pubsub_project_id,
        'standardized-signals-sub'
    )

    messages = wait_for_pubsub_message(
        pubsub_subscriber,
        subscription_path,
        timeout=15,
        max_messages=1
    )

    assert len(messages) > 0, "No messages received from Pub/Sub after 15 seconds"

    # Step 4: Verify the published message format
    standardized_signal = messages[0]

    # Verify required fields (format created by signal_collector._publish_to_microservices)
    assert 'signal_id' in standardized_signal
    assert 'strategy_id' in standardized_signal
    assert 'instrument' in standardized_signal
    assert 'action' in standardized_signal
    assert 'timestamp' in standardized_signal

    # Verify signal content matches what we sent
    assert standardized_signal['strategy_id'] == 'Forex'
    assert standardized_signal['instrument'] == 'AUDNZD'
    assert standardized_signal['action'] in ['ENTRY', 'EXIT']  # Script sends SELL which becomes ENTRY/EXIT

    print(f"✅ Signal published to Pub/Sub: {standardized_signal['signal_id']}")
    print(f"   → Strategy: {standardized_signal['strategy_id']}")
    print(f"   → Instrument: {standardized_signal['instrument']}")
    print(f"   → Action: {standardized_signal['action']}")


def test_signal_collector_mongodb_catchup(
    test_signal_factory,
    signals_collection,
    cleanup_test_signals,
    mongodb_client
):
    """
    Test signal_collector.py's catchup functionality.

    This tests that signal_collector can pick up signals that were
    stored in MongoDB while it was offline (catchup mode).
    """
    from signal_collector import WebhookSignalCollector

    # Step 1: Create a test signal directly in MongoDB (simulating missed signal)
    test_signal = test_signal_factory(
        strategy_name="TestCatchup",
        ticker="TSLA",
        action="BUY",
        price=250.50,
        environment="staging"
    )

    # Insert directly into MongoDB
    signal_doc = {
        'signalID': test_signal['signalID'],
        'strategy_name': test_signal['strategy_name'],
        'timestamp': test_signal['timestamp'],
        'signal': test_signal['signal'],
        'environment': test_signal['environment'],
        'received_at': datetime.utcnow(),
        'signal_processed': False  # Mark as unprocessed
    }

    result = signals_collection.insert_one(signal_doc)
    signal_id = test_signal['signalID']
    cleanup_test_signals(signal_id)

    print(f"✅ Test signal inserted into MongoDB: {signal_id}")

    # Step 2: Create a collector instance and run catchup
    collector = WebhookSignalCollector(
        webhook_url="https://staging.mathematricks.fund",
        mongodb_url=os.getenv('MONGODB_URI')
    )

    # Record how many signals were processed before
    initial_count = len(collector.collected_signals)

    # Run catchup (this should find our test signal)
    collector.fetch_missed_signals_from_mongodb()

    # Step 3: Verify signal was caught up
    assert len(collector.collected_signals) > initial_count, \
        "Signal was not caught up from MongoDB"

    # Verify the caught signal matches what we inserted
    caught_signal = collector.collected_signals[-1]
    assert caught_signal['signal']['strategy_name'] == 'TestCatchup'
    assert caught_signal['signal']['signal']['ticker'] == 'TSLA'
    assert caught_signal['is_catchup'] is True

    print(f"✅ Signal caught up successfully")

    # Step 4: Verify signal was marked as processed
    time.sleep(1)  # Give it a moment to update
    updated_doc = signals_collection.find_one({'signalID': signal_id})
    assert updated_doc.get('signal_processed') is True, \
        "Signal was not marked as processed in MongoDB"

    print(f"✅ Signal marked as processed in MongoDB")


def test_signal_standardization_format(
    test_signal_factory,
    pubsub_publisher,
    pubsub_subscriber,
    pubsub_project_id,
    wait_for_pubsub_message
):
    """
    Test that signal_collector._publish_to_microservices creates correct format.

    This verifies the standardization logic that converts TradingView signals
    to the Cerebro-expected format.
    """
    from signal_collector import WebhookSignalCollector

    # Create a collector instance
    collector = WebhookSignalCollector(
        webhook_url="https://staging.mathematricks.fund",
        mongodb_url=os.getenv('MONGODB_URI')
    )

    # Create a test signal
    test_signal = test_signal_factory(
        strategy_name="FormatTest",
        ticker="GOOGL",
        action="BUY",
        price=140.25,
        quantity=50
    )

    # Call the actual standardization function
    collector._publish_to_microservices(test_signal)

    print(f"✅ Signal published using _publish_to_microservices")

    # Verify the standardized message in Pub/Sub
    subscription_path = pubsub_subscriber.subscription_path(
        pubsub_project_id,
        'standardized-signals-sub'
    )

    messages = wait_for_pubsub_message(
        pubsub_subscriber,
        subscription_path,
        timeout=5,
        max_messages=1
    )

    assert len(messages) > 0, "Standardized signal not found in Pub/Sub"

    standardized = messages[0]

    # Verify all required fields exist
    required_fields = [
        'signal_id', 'strategy_id', 'timestamp', 'instrument',
        'direction', 'action', 'order_type', 'price', 'quantity',
        'stop_loss', 'take_profit', 'metadata', 'processed_by_cerebro',
        'created_at'
    ]

    for field in required_fields:
        assert field in standardized, f"Missing required field: {field}"

    # Verify data types
    assert isinstance(standardized['price'], (int, float))
    assert isinstance(standardized['quantity'], (int, float))
    assert isinstance(standardized['processed_by_cerebro'], bool)
    assert standardized['processed_by_cerebro'] is False  # Should be False initially

    # Verify signal ID format: {strategy}_{YYYYMMDD}_{HHMMSS}_{seq}
    signal_id_parts = standardized['signal_id'].split('_')
    assert len(signal_id_parts) == 4, \
        f"Signal ID format incorrect: {standardized['signal_id']}"
    assert signal_id_parts[0] == 'FormatTest'
    assert len(signal_id_parts[1]) == 8  # YYYYMMDD
    assert len(signal_id_parts[2]) == 6  # HHMMSS
    assert len(signal_id_parts[3]) == 3  # sequence number

    print(f"✅ Standardized signal format verified")
    print(f"   → Signal ID: {standardized['signal_id']}")
    print(f"   → Format: {{strategy}}_{{YYYYMMDD}}_{{HHMMSS}}_{{seq}}")


def test_signal_environment_filtering(
    test_signal_factory,
    signals_collection,
    cleanup_test_signals
):
    """
    Test that signal_collector correctly filters signals by environment.

    A staging collector should only process staging signals,
    not production signals.
    """
    from signal_collector import WebhookSignalCollector

    # Create a staging collector
    staging_collector = WebhookSignalCollector(
        webhook_url="https://staging.mathematricks.fund",
        mongodb_url=os.getenv('MONGODB_URI')
    )

    # Insert a production signal into MongoDB
    prod_signal = test_signal_factory(
        strategy_name="ProdOnly",
        ticker="MSFT",
        action="SELL",
        environment="production"  # This is production
    )

    prod_doc = {
        'signalID': prod_signal['signalID'],
        'strategy_name': prod_signal['strategy_name'],
        'signal': prod_signal['signal'],
        'environment': 'production',
        'received_at': datetime.utcnow(),
        'signal_processed': False
    }

    signals_collection.insert_one(prod_doc)
    cleanup_test_signals(prod_signal['signalID'])

    # Insert a staging signal into MongoDB
    staging_signal = test_signal_factory(
        strategy_name="StagingOnly",
        ticker="AMZN",
        action="BUY",
        environment="staging"  # This is staging
    )

    staging_doc = {
        'signalID': staging_signal['signalID'],
        'strategy_name': staging_signal['strategy_name'],
        'signal': staging_signal['signal'],
        'environment': 'staging',
        'received_at': datetime.utcnow(),
        'signal_processed': False
    }

    signals_collection.insert_one(staging_doc)
    cleanup_test_signals(staging_signal['signalID'])

    print(f"✅ Inserted 1 production signal and 1 staging signal")

    # Run catchup
    initial_count = len(staging_collector.collected_signals)
    staging_collector.fetch_missed_signals_from_mongodb()

    # Verify only staging signal was processed
    new_signals = staging_collector.collected_signals[initial_count:]

    assert len(new_signals) == 1, \
        f"Expected 1 signal, got {len(new_signals)} (should filter by environment)"

    assert new_signals[0]['signal']['strategy_name'] == 'StagingOnly', \
        "Wrong signal processed - should only get staging signal"

    print(f"✅ Environment filtering working correctly")
    print(f"   → Staging collector only processed staging signal")
    print(f"   → Production signal was ignored")
