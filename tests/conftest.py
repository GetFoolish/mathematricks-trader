"""
Pytest configuration and shared fixtures for Mathematricks Trader tests.

CRITICAL: These fixtures provide access to REAL production code.
Tests MUST import from main codebase, never reimplement logic.
"""
import os
import sys
import json
import pytest
import time
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
from pymongo import MongoClient
from google.cloud import pubsub_v1

# Add project root to path to allow imports from services
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# ============================================================================
# MongoDB Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def mongodb_uri():
    """Get MongoDB connection string from environment"""
    uri = os.getenv('MONGODB_URI', 'mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/')
    return uri


@pytest.fixture(scope="session")
def mongodb_client(mongodb_uri):
    """Create MongoDB client for testing"""
    client = MongoClient(
        mongodb_uri,
        tls=True,
        tlsAllowInvalidCertificates=True  # For development only
    )
    # Test connection
    client.admin.command('ping')
    yield client
    client.close()


@pytest.fixture
def signals_collection(mongodb_client):
    """Get trading signals collection"""
    db = mongodb_client['mathematricks_signals']
    return db['trading_signals']


@pytest.fixture
def strategies_collection(mongodb_client):
    """Get strategies collection"""
    db = mongodb_client['mathematricks_strategies']
    return db['strategies']


@pytest.fixture
def orders_collection(mongodb_client):
    """Get orders collection"""
    db = mongodb_client['mathematricks_orders']
    return db['orders']


@pytest.fixture
def account_state_collection(mongodb_client):
    """Get account state collection"""
    db = mongodb_client['mathematricks_account']
    return db['account_state']


# ============================================================================
# Google Pub/Sub Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def pubsub_project_id():
    """Get GCP project ID from environment"""
    return os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')


@pytest.fixture(scope="session")
def pubsub_emulator_host():
    """Set Pub/Sub emulator host for testing"""
    emulator_host = 'localhost:8085'
    os.environ['PUBSUB_EMULATOR_HOST'] = emulator_host
    return emulator_host


@pytest.fixture
def pubsub_publisher(pubsub_emulator_host, pubsub_project_id):
    """Create Pub/Sub publisher client"""
    # Ensure emulator is used
    os.environ['PUBSUB_EMULATOR_HOST'] = pubsub_emulator_host
    publisher = pubsub_v1.PublisherClient()
    yield publisher


@pytest.fixture
def pubsub_subscriber(pubsub_emulator_host, pubsub_project_id):
    """Create Pub/Sub subscriber client"""
    # Ensure emulator is used
    os.environ['PUBSUB_EMULATOR_HOST'] = pubsub_emulator_host
    subscriber = pubsub_v1.SubscriberClient()
    yield subscriber


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest.fixture
def cerebro_api_url():
    """CerebroService API base URL"""
    return os.getenv('CEREBRO_API_URL', 'http://localhost:8001')


@pytest.fixture
def account_data_api_url():
    """AccountDataService API base URL"""
    return os.getenv('ACCOUNT_DATA_API_URL', 'http://localhost:8002')


@pytest.fixture
def execution_api_url():
    """ExecutionService API base URL (if it has REST endpoints)"""
    return os.getenv('EXECUTION_API_URL', 'http://localhost:8003')


# ============================================================================
# Test Data Factory Fixtures
# ============================================================================

@pytest.fixture
def test_signal_factory():
    """
    Factory for creating test signals.
    Returns a function that generates signal data in the correct format.
    """
    def _create_signal(
        strategy_name: str = "TestStrategy",
        ticker: str = "AAPL",
        action: str = "BUY",
        price: float = 150.25,
        quantity: int = 100,
        environment: str = "staging"
    ) -> Dict[str, Any]:
        """
        Create a test signal in TradingView format.
        This matches the format expected by signal_collector.py
        """
        timestamp = datetime.utcnow().isoformat()
        signal_id = f"{strategy_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        return {
            "passphrase": "yahoo123",
            "timestamp": timestamp,
            "signalID": signal_id,
            "strategy_name": strategy_name,
            "environment": environment,
            "signal": {
                "ticker": ticker,
                "instrument": ticker,
                "action": action,
                "price": price,
                "quantity": quantity,
                "order_type": "MARKET"
            }
        }

    return _create_signal


@pytest.fixture
def test_standardized_signal_factory():
    """
    Factory for creating standardized signals (Cerebro format).
    Returns a function that generates signals in the format expected by CerebroService.
    """
    def _create_standardized_signal(
        strategy_id: str = "TestStrategy",
        instrument: str = "AAPL",
        direction: str = "LONG",
        action: str = "ENTRY",
        price: float = 150.25,
        quantity: float = 100.0
    ) -> Dict[str, Any]:
        """
        Create a standardized signal in Cerebro format.
        This matches the format published to the 'standardized-signals' topic.
        """
        now = datetime.utcnow()
        signal_id = f"{strategy_id}_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000:03d}"

        return {
            "signal_id": signal_id,
            "strategy_id": strategy_id,
            "timestamp": now.isoformat(),
            "instrument": instrument,
            "direction": direction,
            "action": action,
            "order_type": "MARKET",
            "price": price,
            "quantity": quantity,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "expiry": None,
            "instrument_type": None,
            "underlying": None,
            "legs": None,
            "exchange": None,
            "metadata": {
                "expected_alpha": 0.02
            },
            "processed_by_cerebro": False,
            "created_at": now.isoformat()
        }

    return _create_standardized_signal


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture
def cleanup_test_signals(signals_collection):
    """
    Cleanup fixture that removes test signals after each test.
    Runs after the test completes (yield).
    """
    test_signal_ids = []

    def _register_signal_id(signal_id: str):
        """Register a signal ID for cleanup"""
        test_signal_ids.append(signal_id)

    yield _register_signal_id

    # Cleanup: Remove all test signals
    if test_signal_ids:
        signals_collection.delete_many({"signalID": {"$in": test_signal_ids}})


@pytest.fixture
def cleanup_test_orders(orders_collection):
    """
    Cleanup fixture that removes test orders after each test.
    """
    test_order_ids = []

    def _register_order_id(order_id: str):
        """Register an order ID for cleanup"""
        test_order_ids.append(order_id)

    yield _register_order_id

    # Cleanup: Remove all test orders
    if test_order_ids:
        orders_collection.delete_many({"order_id": {"$in": test_order_ids}})


@pytest.fixture
def cleanup_test_strategies(strategies_collection):
    """
    Cleanup fixture that removes test strategies after each test.
    """
    test_strategy_ids = []

    def _register_strategy_id(strategy_id: str):
        """Register a strategy ID for cleanup"""
        test_strategy_ids.append(strategy_id)

    yield _register_strategy_id

    # Cleanup: Remove all test strategies
    if test_strategy_ids:
        strategies_collection.delete_many({"strategy_id": {"$in": test_strategy_ids}})


# ============================================================================
# Helper Functions (as fixtures)
# ============================================================================

@pytest.fixture
def wait_for_pubsub_message():
    """
    Helper function to wait for a Pub/Sub message with timeout.
    Returns a function that can be called to wait for messages.
    """
    def _wait(
        subscriber,
        subscription_path: str,
        timeout: int = 10,
        max_messages: int = 1
    ) -> list:
        """
        Pull messages from subscription with timeout.
        Returns list of messages received.
        """
        messages = []
        start_time = time.time()

        while time.time() - start_time < timeout and len(messages) < max_messages:
            try:
                response = subscriber.pull(
                    request={
                        "subscription": subscription_path,
                        "max_messages": max_messages,
                    },
                    timeout=2.0
                )

                for received_message in response.received_messages:
                    # Decode message
                    data = json.loads(received_message.message.data.decode('utf-8'))
                    messages.append(data)

                    # Acknowledge message
                    subscriber.acknowledge(
                        request={
                            "subscription": subscription_path,
                            "ack_ids": [received_message.ack_id],
                        }
                    )

                if len(messages) >= max_messages:
                    break

            except Exception as e:
                # Timeout or no messages
                time.sleep(0.5)
                continue

        return messages

    return _wait


@pytest.fixture
def wait_for_mongodb_document():
    """
    Helper function to wait for a MongoDB document with timeout.
    Returns a function that can be called to wait for documents.
    """
    def _wait(
        collection,
        query: Dict[str, Any],
        timeout: int = 10
    ):
        """
        Wait for a document matching query to appear in MongoDB.
        Returns the document or None if timeout.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            document = collection.find_one(query)
            if document:
                return document
            time.sleep(0.5)

        return None

    return _wait


# ============================================================================
# Service Health Check Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def ensure_services_running():
    """
    Session-level fixture that checks if required services are running.
    Fails fast if services are not available.

    Note: After Phase 3.5, CerebroService no longer has HTTP endpoints.
    It runs as a background Pub/Sub consumer, so we only check services with health endpoints.
    """
    import requests

    services = {
        # Phase 3.5: CerebroService no longer has HTTP/health endpoint (Pub/Sub consumer only)
        'AccountDataService': 'http://localhost:8002/health',
        'Pub/Sub Emulator': 'http://localhost:8085',
    }

    failed_services = []

    for service_name, url in services.items():
        try:
            response = requests.get(url, timeout=2)
            if response.status_code != 200:
                failed_services.append(service_name)
        except Exception:
            failed_services.append(service_name)

    if failed_services:
        pytest.skip(
            f"Required services not running: {', '.join(failed_services)}\n"
            f"Run './run_mvp_demo.sh' to start services."
        )

    yield
