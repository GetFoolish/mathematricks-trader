"""
Execution Service - MVP
Connects to IBKR broker, executes orders, and reports back execution confirmations and account state.
"""
import os
import sys
import logging
import json
import argparse
from datetime import datetime, time as dt_time
from typing import Dict, Any, Optional, List
from pymongo import MongoClient
from dotenv import load_dotenv
import threading
import time
import queue
import requests
import pytz
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Add services directory to path so we can import brokers package
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
SERVICES_PATH = os.path.join(PROJECT_ROOT, 'services')
sys.path.insert(0, SERVICES_PATH)

# Import broker library
from brokers import BrokerFactory, OrderSide, OrderType, OrderStatus
from brokers.exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    BrokerAPIError,
    InvalidSymbolError
)

# Import Telegram notifier
from telegram.notifier import TelegramNotifier

# Import for health checks
import socket

# Load environment variables from project root
env_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(env_path)

# Configure logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Create custom formatter matching Cerebro format
custom_formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')

# Create file handler with custom format
file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'execution_service.log'))
file_handler.setFormatter(custom_formatter)

# Create console handler with same format
console_handler = logging.StreamHandler()
console_handler.setFormatter(custom_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Signal processing log handler - unified log for complete signal journey
signal_processing_handler = logging.FileHandler(os.path.join(LOG_DIR, 'signal_processing.log'))
signal_processing_handler.setLevel(logging.INFO)
signal_processing_formatter = logging.Formatter(
    '%(asctime)s | [EXECUTION] | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
signal_processing_handler.setFormatter(signal_processing_formatter)
# Only log signal-related events to this file (filtered later)
signal_processing_handler.addFilter(lambda record: 'SIGNAL:' in record.getMessage() or 'ORDER:' in record.getMessage())

# Add signal processing handler
signal_logger = logging.getLogger('signal_processing')
signal_logger.addHandler(signal_processing_handler)
signal_logger.setLevel(logging.INFO)

# ========================================================================
# COMMAND-LINE ARGUMENTS
# ========================================================================

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Execution Service - Order Execution Engine')
parser.add_argument('--use-mock-broker', action='store_true',
                    help='Use Mock broker for all orders (testing mode, overrides strategy account routing)')
args = parser.parse_args()

# Log mode
if args.use_mock_broker:
    logger.warning("=" * 80)
    logger.warning("🧪 MOCK MODE ENABLED: All orders will be routed to Mock_Paper broker")
    logger.warning("=" * 80)

# ========================================================================
# DATABASE INITIALIZATION
# ========================================================================

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
if not mongo_uri:
    raise ValueError("MONGODB_URI environment variable is not set - check .env file")

# Only use TLS for remote MongoDB Atlas connections (not localhost)
use_tls = 'mongodb+srv' in mongo_uri or 'mongodb.net' in mongo_uri
if use_tls:
    mongo_client = MongoClient(
        mongo_uri,
        tls=True,
        tlsAllowInvalidCertificates=True  # For development only
    )
else:
    mongo_client = MongoClient(mongo_uri)  # No TLS for localhost
db = mongo_client['mathematricks_trading']
# execution_confirmations collection removed - execution data stored in signal_store.execution field
trading_orders_collection = db['trading_orders']
trading_accounts_collection = db['trading_accounts']  # For position tracking
signal_store_collection = db['signal_store']  # For updating execution data

# Pub/Sub removed - using MongoDB Change Streams instead
# All event-driven communication now via MongoDB

# Account Data Service Configuration
ACCOUNT_DATA_SERVICE_URL = os.getenv('ACCOUNT_DATA_SERVICE_URL', 'http://localhost:8082')

# Gateway Controller for IBKR accounts
from services.execution_service.gateway_controller import GatewayController
gateway_controller = GatewayController()

# Telegram Notifier
telegram = TelegramNotifier()
logger.info(f"Telegram notifications: {'enabled' if telegram.enabled else 'disabled'}")


# ========================================================================
# FASTAPI HEALTH CHECK SERVER
# ========================================================================

# Global service status
service_status = {
    'ready': False,
    'broker_pool_size': 0,
    'brokers_connected': 0,
    'change_stream_connected': False,
    'pending_orders_processed': 0
}

# Create FastAPI app for health checks
app = FastAPI(title="Execution Service", version="1.0")

@app.get('/health')
def health_check():
    """Health check endpoint"""
    if service_status['ready']:
        return {
            'status': 'healthy',
            'ready': True,
            **service_status
        }
    else:
        return JSONResponse(
            status_code=503,
            content={
                'status': 'starting',
                'ready': False,
                **service_status
            }
        )

@app.get('/status')
def status_check():
    """Detailed status endpoint"""
    return {
        **service_status,
        'broker_pool': list(broker_pool.keys()) if 'broker_pool' in globals() else []
    }

# Pydantic models for API requests
class ExecuteOrderRequest(BaseModel):
    # Accept full order data from cerebro (not just order_id)
    order_id: str
    signal_id: Optional[str] = None
    mathematricks_signal_id: Optional[str] = None
    raw_signal_mongodb_id: Optional[str] = None
    strategy_id: Optional[str] = None
    fund_id: Optional[str] = None
    account_id: Optional[str] = None
    account: Optional[str] = None
    timestamp: Optional[str] = None
    instrument: Optional[str] = None
    direction: Optional[str] = None
    action: Optional[str] = None
    signal_type: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    expiry: Optional[str] = None
    instrument_type: Optional[str] = None
    underlying: Optional[str] = None
    exchange: Optional[str] = None
    leg_index: Optional[int] = None
    total_legs: Optional[int] = None
    is_multi_leg: Optional[bool] = None
    allocation_name: Optional[str] = None
    account_allocated_capital: Optional[float] = None
    cerebro_decision: Optional[dict] = None
    environment: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    entry_signal_id: Optional[str] = None
    entry_signal_ref: Optional[dict] = None
    
    class Config:
        extra = "allow"  # Allow additional fields

class ExecuteOrderResponse(BaseModel):
    status: str
    order_id: str
    message: str

@app.post('/api/v1/execute-order', response_model=ExecuteOrderResponse)
def execute_order_endpoint(request: ExecuteOrderRequest):
    """
    Execute a trading order.
    Called by cerebro after creating order data.
    
    Args:
        request: ExecuteOrderRequest containing full order details
    
    Returns:
        ExecuteOrderResponse with status and message
    """
    try:
        logger.info(f"📥 API Request: Execute order {request.order_id}")
        
        # Convert request to dict for processing
        order_data = request.dict()
        
        # Add to queue for processing
        order_queue.put({'order_data': order_data})
        
        logger.info(f"✅ Order {request.order_id} queued for execution")
        
        return ExecuteOrderResponse(
            status="queued",
            order_id=request.order_id,
            message=f"Order {request.order_id} queued for execution"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🚨 ERROR queuing order {request.order_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error queuing order: {str(e)}")

def run_fastapi_server():
    """Run FastAPI server in background thread"""
    uvicorn.run(app, host='0.0.0.0', port=8083, log_level='error')


# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

def is_market_hours(instrument_type: str = "STOCK") -> Dict[str, Any]:
    """
    Check if current time is during market hours.

    Args:
        instrument_type: Type of instrument (STOCK, FOREX, CRYPTO, etc.)

    Returns:
        Dict with:
          - is_open: bool (True if market is open)
          - message: str (human-readable status)
          - current_time_et: str (current time in ET)
    """
    # Get current time in Eastern Time (US stock market timezone)
    et_tz = pytz.timezone('America/New_York')
    now_et = datetime.now(et_tz)
    current_time = now_et.time()

    # Stock market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
    if instrument_type == "STOCK":
        market_open = dt_time(9, 30)  # 9:30 AM
        market_close = dt_time(16, 0)  # 4:00 PM

        # Check if weekend
        if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
            return {
                "is_open": False,
                "message": f"⚠️  Weekend (market closed). Current time: {now_et.strftime('%A %I:%M %p ET')}",
                "current_time_et": now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')
            }

        # Check if within market hours
        if market_open <= current_time <= market_close:
            return {
                "is_open": True,
                "message": f"✅ Market is OPEN. Current time: {now_et.strftime('%I:%M %p ET')}",
                "current_time_et": now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')
            }
        elif current_time < market_open:
            return {
                "is_open": False,
                "message": f"⚠️  Pre-market (opens at 9:30 AM ET). Current time: {now_et.strftime('%I:%M %p ET')}",
                "current_time_et": now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')
            }
        else:
            return {
                "is_open": False,
                "message": f"⚠️  After-hours (closed at 4:00 PM ET). Current time: {now_et.strftime('%I:%M %p ET')}",
                "current_time_et": now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')
            }

    # FOREX and CRYPTO trade 24/7 (mostly)
    elif instrument_type in ["FOREX", "CRYPTO"]:
        return {
            "is_open": True,
            "message": f"✅ {instrument_type} market is open (24/7)",
            "current_time_et": now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')
        }

    # Default: assume market is open (for unknown instrument types)
    return {
        "is_open": True,
        "message": f"Market hours unknown for {instrument_type} (assuming open)",
        "current_time_et": now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')
    }


def log_open_positions(account_id: str, label: str):
    """
    Log open positions for an account to help debug position tracking.

    Args:
        account_id: Account ID to query
        label: Label for the log message (e.g., "BEFORE ORDER", "AFTER ORDER")
    """
    try:
        account = trading_accounts_collection.find_one({"account_id": account_id})
        if account:
            all_positions = account.get('open_positions', [])
            # Filter to only show OPEN positions (not CLOSED)
            open_positions = [p for p in all_positions if p.get('status') == 'OPEN']
            if open_positions:
                logger.info(f"📊 OPEN POSITIONS [{label}] for {account_id}:")
                for pos in open_positions:
                    symbol = pos.get('instrument', '?')
                    qty = pos.get('quantity', 0)
                    avg_price = pos.get('avg_entry_price', 0)
                    strategy = pos.get('strategy_id', '?')
                    logger.info(f"   - {symbol}: {qty} shares @ ${avg_price:.2f} | Strategy: {strategy}")
            else:
                logger.info(f"📊 OPEN POSITIONS [{label}] for {account_id}: (none)")
        else:
            logger.warning(f"📊 OPEN POSITIONS [{label}]: Account {account_id} not found in database")
    except Exception as e:
        logger.error(f"Error logging open positions: {e}")

# ========================================================================
# BROKER POOL - Multi-Broker Architecture
# ========================================================================

# Broker pool: {account_id: broker_instance}
broker_pool = {}


def get_active_accounts_from_service() -> List[Dict[str, Any]]:
    """
    Query AccountDataService for all active accounts.

    Returns:
        List of active account dictionaries
    """
    try:
        response = requests.get(f"{ACCOUNT_DATA_SERVICE_URL}/api/v1/accounts")
        response.raise_for_status()
        accounts_data = response.json()

        # Filter for ACTIVE accounts only
        active_accounts = [
            acc for acc in accounts_data.get('accounts', [])
            if acc.get('status') == 'ACTIVE'
        ]

        logger.info(f"Found {len(active_accounts)} active accounts from AccountDataService")
        return active_accounts

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get accounts from AccountDataService: {str(e)}")
        logger.warning("Falling back to single IBKR broker configuration")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting accounts: {str(e)}")
        return []


def _build_broker_config(broker_name: str, account_id: str, auth_details: Dict) -> Dict:
    """
    Build broker-specific configuration from authentication_details.
    
    Supports: IBKR, Binance, Bybit, Alpaca, Oanda
    """
    config = {
        "broker": broker_name,
        "account_id": account_id
    }
    
    if broker_name == 'IBKR':
        # IBKR: host, port, client_id, market_data_type (optional) from auth_details
        config.update({
            "host": auth_details.get('host', 'host.docker.internal'),
            "port": auth_details.get('port', 4002),
            "client_id": auth_details.get('client_id', 1)
        })
        # Add market_data_type if specified
        if 'market_data_type' in auth_details:
            config['market_data_type'] = auth_details['market_data_type']
    
    elif broker_name == 'Binance':
        # Binance: api_key, api_secret, testnet
        config.update({
            "api_key": auth_details.get('api_key'),
            "api_secret": auth_details.get('api_secret'),
            "testnet": auth_details.get('testnet', False)
        })
    
    elif broker_name == 'Bybit':
        # Bybit: api_key, api_secret, testnet
        config.update({
            "api_key": auth_details.get('api_key'),
            "api_secret": auth_details.get('api_secret'),
            "testnet": auth_details.get('testnet', False)
        })
    
    elif broker_name == 'Alpaca':
        # Alpaca: api_key, api_secret, paper
        config.update({
            "api_key": auth_details.get('api_key'),
            "api_secret": auth_details.get('api_secret'),
            "paper": auth_details.get('paper', True)
        })
    
    elif broker_name == 'Oanda':
        # Oanda: api_key, account_id, practice
        config.update({
            "api_key": auth_details.get('api_key'),
            "practice": auth_details.get('practice', True)
        })
    
    elif broker_name == 'Mock':
        # Mock: No special auth needed, pass through any provided details
        config.update(auth_details)
    
    else:
        # Unknown broker - pass through auth_details
        logger.warning(f"Unknown broker type: {broker_name}, passing through auth_details")
        config.update(auth_details)
    
    return config


def load_gateway_config() -> List[str]:
    """Load always-start account IDs from gateway_config.yml"""
    import yaml
    from pathlib import Path
    
    config_path = Path(__file__).parent / "gateway_config.yml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('always_start_accounts', [])
    except Exception as e:
        logger.warning(f"Could not load gateway_config.yml: {e}")
        return []


def start_required_gateways(accounts: List[Dict]):
    """
    Start IB Gateway containers for IBKR accounts that need them.
    
    Starts gateways for:
    1. Accounts listed in gateway_config.yml (always-start)
    2. Accounts with open positions
    """
    # Load always-start accounts
    always_start = load_gateway_config()
    logger.info(f"Always-start accounts from config: {always_start}")
    
    # Find accounts with open positions
    accounts_with_positions = []
    for account in accounts:
        if account['broker'] == 'IBKR':
            try:
                # Query MongoDB for open positions
                positions = list(trading_accounts_collection.find_one(
                    {"account_id": account['account_id']},
                    {"open_positions": 1}
                ).get('open_positions', []))
                
                if len(positions) > 0:
                    accounts_with_positions.append(account['account_id'])
            except Exception as e:
                logger.debug(f"Could not check positions for {account['account_id']}: {e}")
    
    if accounts_with_positions:
        logger.info(f"Accounts with open positions: {accounts_with_positions}")
    
    # Combine lists (deduplicate)
    accounts_to_start = set(always_start + accounts_with_positions)
    
    if not accounts_to_start:
        logger.info("No IBKR gateways needed at startup")
        return
    
    logger.info(f"🚀 Starting IB Gateways for {len(accounts_to_start)} account(s)...")
    
    # Start gateway for each account
    for account_id in accounts_to_start:
        # Find account in accounts list
        account = next((a for a in accounts if a['account_id'] == account_id), None)
        
        if not account:
            logger.warning(f"Account {account_id} not found in AccountDataService")
            continue
        
        if account['broker'] != 'IBKR':
            logger.info(f"Skipping {account_id} - not an IBKR account")
            continue
        
        # Create gateway
        success = gateway_controller.create_gateway_for_account(account)
        
        if success:
            logger.info(f"✅ Gateway ready for {account_id}")
        else:
            logger.error(f"❌ Failed to start gateway for {account_id}")


def check_gateway_health(host: str, port: int, timeout: int = 2) -> bool:
    """
    Check if IB Gateway API is ready by attempting an actual API connection.
    This is more reliable than just checking if the port is open.
    
    Args:
        host: Gateway hostname (container name or IP)
        port: API port (4002 for paper, 4001 for live)
        timeout: Connection timeout in seconds
        
    Returns:
        True if gateway API is ready and responding, False otherwise
    """
    try:
        from ib_insync import IB
        
        # Create temporary IB connection
        ib = IB()
        
        # Try to connect with a short timeout
        # Use a high client_id to avoid conflicts with actual broker connections
        test_client_id = 9999
        
        try:
            ib.connect(host, port, clientId=test_client_id, timeout=timeout)
            
            # If we get here, API is ready
            is_connected = ib.isConnected()
            ib.disconnect()
            
            return is_connected
            
        except Exception as e:
            # API not ready yet (TimeoutError, connection refused, etc.)
            try:
                ib.disconnect()
            except:
                pass
            return False
            
    except Exception:
        # Fallback to simple socket check if ib_insync fails
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False


def wait_for_gateways_ready(accounts: List[Dict], max_wait: int = 60) -> None:
    """
    Wait for all IBKR gateways to be ready with health checks.
    
    Args:
        accounts: List of account configurations
        max_wait: Maximum time to wait in seconds (default 60)
    """
    # Find all IBKR accounts that need gateways
    ibkr_accounts = [acc for acc in accounts if acc.get('broker') == 'IBKR']
    
    if not ibkr_accounts:
        logger.info("No IBKR accounts - skipping gateway health checks")
        return
    
    logger.info(f"⏳ Checking health of {len(ibkr_accounts)} IB Gateway(s)...")
    
    start_time = time.time()
    check_interval = 2  # Check every 2 seconds
    
    while time.time() - start_time < max_wait:
        all_ready = True
        
        for account in ibkr_accounts:
            account_id = account.get('account_id')
            auth = account.get('authentication_details', {})
            
            # Get gateway host and port
            host = auth.get('host', f"ib-gateway-{account_id.lower().replace('_', '-')}")
            port = auth.get('port', 4004)  # Default to paper port
            
            if not check_gateway_health(host, port):
                all_ready = False
                elapsed = int(time.time() - start_time)
                logger.debug(f"   Gateway {account_id} not ready yet (elapsed: {elapsed}s)")
                break
        
        if all_ready:
            elapsed = int(time.time() - start_time)
            logger.info(f"✅ All IB Gateways ready in {elapsed} seconds")
            # Small grace period to let API fully stabilize after first successful connection
            if elapsed < 5:
                grace_period = 3
                logger.info(f"   Waiting {grace_period}s grace period for API stabilization...")
                time.sleep(grace_period)
            return
        
        time.sleep(check_interval)
    
    # Timeout reached
    elapsed = int(time.time() - start_time)
    logger.warning(f"⚠️ Gateway health check timeout after {elapsed}s - proceeding anyway")
    logger.warning("   Some gateways may not be fully ready yet")


def initialize_broker_pool():
    """
    Initialize broker pool by creating broker instances for all active accounts.
    Supports multi-broker architecture: IBKR, Binance, Bybit, Alpaca, Oanda, Mock
    Supports 4-mode trading system: mock_mock, mock_live, paper_live, live_live.

    Mode handling (computed from account_type × data_source):
    - mock_mock: Create only Mock broker (fast testing)
    - mock_live: Create real broker + Mock, wrap in BrokerModeAdapter
    - paper_live: Create only real broker (IBKR paper account on port 4004)
    - live_live: Create only real broker (production trading)

    For IBKR accounts: Creates IB Gateway containers as needed
    For other brokers: Uses API keys from MongoDB authentication_details
    """
    global broker_pool

    logger.info("Initializing broker pool from AccountDataService...")

    # Get active accounts
    accounts = get_active_accounts_from_service()

    if not accounts:
        logger.warning("⚠️ No accounts from AccountDataService - broker pool will be empty")
        logger.warning("⚠️ Execution service will not be able to execute orders until accounts are configured")
        return

    # Start IBKR gateways for accounts that need them
    start_required_gateways(accounts)
    
    # Wait for gateways to be ready (with health checks)
    wait_for_gateways_ready(accounts, max_wait=60)

    # Track initialized brokers for summary log
    initialized_brokers = []

    # Create broker instance for each active account
    for account in accounts:
        account_id = account.get('account_id')
        broker_name = account.get('broker')
        auth_details = account.get('authentication_details', {})
        
        # Get mode (can be string or list)
        mode = account.get('mode')
        
        # Convert mode to list if it's a string (backward compatibility)
        if isinstance(mode, str):
            modes = [mode]
        elif isinstance(mode, list):
            modes = mode
        else:
            logger.error(f"Account {account_id} has invalid mode field: {mode}. Skipping.")
            continue
        
        # For backward compatibility, use first mode to determine broker type
        # In future, we could create multiple broker instances for multi-mode accounts
        primary_mode = modes[0]
        mode_parts = primary_mode.split('_')
        if len(mode_parts) != 2:
            logger.error(f"Account {account_id} has invalid mode format: {primary_mode}. Expected format: <account_type>_<data_source>")
            continue
        
        account_type, data_source = mode_parts
        computed_mode = primary_mode

        try:
            # Build broker-specific config
            real_config = _build_broker_config(broker_name, account_id, auth_details)
            
            if account_type == 'mock' and data_source == 'mock':
                # mock_mock: Create only Mock broker
                broker_config = {
                    "broker": "Mock",
                    "account_id": account_id,
                    **auth_details
                }
                broker_instance = BrokerFactory.create_broker(broker_config)

            elif account_type == 'mock' and data_source == 'live':
                # mock_live: Create BOTH real broker + Mock, wrap in BrokerModeAdapter
                # Create real broker
                real_broker = BrokerFactory.create_broker(real_config)

                # Create mock broker in read-only mode (prevents MongoDB config overwrites)
                mock_config = {
                    "broker": "Mock",
                    "account_id": account_id,
                    "read_only": True,
                    **auth_details
                }
                mock_broker = BrokerFactory.create_broker(mock_config)

                # Wrap in BrokerModeAdapter
                from services.brokers.adapters import BrokerModeAdapter
                broker_instance = BrokerModeAdapter(
                    real_broker, 
                    mock_broker, 
                    account_type='mock',
                    data_source='live'
                )

            elif account_type == 'paper' and data_source == 'live':
                # paper_live: Create only real broker (IBKR paper account on port 4004)
                broker_instance = BrokerFactory.create_broker(real_config)

            elif account_type == 'live' and data_source == 'live':
                # live_live: Create only real broker (production)
                broker_instance = BrokerFactory.create_broker(real_config)

            else:
                logger.error(f"❌ Invalid mode: account_type='{account_type}', data_source='{data_source}' for account {account_id}. Skipping.")
                continue

            # Add to broker pool
            broker_pool[account_id] = broker_instance
            
            # Track for summary
            broker_display = f"{broker_name}+Mock" if account_type == 'mock' and data_source == 'live' else broker_name
            initialized_brokers.append(f"{account_id} ({broker_display}, modes: {','.join(modes)})")

        except Exception as e:
            logger.error(f"❌ Failed to create broker for account {account_id}: {str(e)}")
            logger.error(f"   broker={broker_name}, account_type={account_type}, data_source={data_source}")
            import traceback
            logger.error(traceback.format_exc())
            continue

    # Summary log
    if initialized_brokers:
        logger.info(f"✅ Broker pool initialized with {len(broker_pool)} broker(s):")
        for broker_info in initialized_brokers:
            logger.info(f"   • {broker_info}")
    else:
        logger.warning("⚠️ Broker pool is empty - no brokers initialized")


def get_broker_for_account(account_id: str) -> Optional['AbstractBroker']:
    """
    Get broker instance for specific account.

    Args:
        account_id: Account ID (e.g., "IBKR_Paper", "Mock_Paper")

    Returns:
        Broker instance, or None if not found
    """
    if account_id not in broker_pool:
        logger.error(f"❌ No broker found for account: {account_id}")
        logger.error(f"   Available accounts: {list(broker_pool.keys())}")
        return None

    return broker_pool[account_id]


# Initialize broker pool on startup
initialize_broker_pool()

# Order queue for threading safety
# MongoDB Change Stream watcher runs in thread, orders are processed in main thread
order_queue = queue.Queue()

# Track active IBKR orders by order_id for cancellation
active_ibkr_orders = {}  # {order_id: broker_order_id}

# 🚨 CRITICAL FAILSAFE: Track processed signal IDs to prevent duplicate execution
processed_signal_ids = set()  # In-memory deduplication
SIGNAL_ID_EXPIRY_HOURS = 24  # Keep signal IDs for 24 hours


def connect_all_brokers():
    """
    Connect to all brokers in the broker pool.
    In mock mode, only connect to Mock broker (skip real brokers like IBKR).
    """
    logger.info(f"Connecting to {len(broker_pool)} broker(s)...")

    success_count = 0
    for account_id, broker_instance in broker_pool.items():
        # In mock mode, skip non-Mock brokers to avoid unnecessary connection attempts
        if args.use_mock_broker and broker_instance.broker_name != "Mock":
            logger.info(f"⏭️ Skipping {broker_instance.broker_name} connection for {account_id} (mock mode)")
            continue

        try:
            if not broker_instance.is_connected():
                logger.info(f"Connecting to {broker_instance.broker_name} for account {account_id}...")
                success = broker_instance.connect()
                if success:
                    logger.info(f"✅ Connected to {broker_instance.broker_name} for {account_id}")
                    success_count += 1
                else:
                    logger.error(f"❌ Failed to connect to {broker_instance.broker_name} for {account_id}")
            else:
                logger.info(f"Already connected to {broker_instance.broker_name} for {account_id}")
                success_count += 1

        except BrokerConnectionError as e:
            logger.error(f"❌ Broker connection error for {account_id}: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting {account_id}: {str(e)}")

    logger.info(f"Broker pool connection complete: {success_count}/{len(broker_pool)} connected")
    return success_count > 0


def submit_order_to_broker(order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Submit order to broker using broker pool (multi-broker routing).

    Routes order to correct broker based on order['account'] field.
    In mock mode (--use-mock-broker), overrides all routing to Mock_Paper.
    """
    try:
        # Get account from order
        account_id = order_data.get('account')
        if not account_id:
            logger.error(f"❌ Order {order_data.get('order_id')} missing 'account' field - cannot route to broker")
            return None

        # MARKET HOURS CHECK: Warn if placing orders outside market hours
        instrument_type = order_data.get('instrument_type', 'STOCK')
        market_status = is_market_hours(instrument_type)
        if not market_status['is_open']:
            logger.warning(f"⏰ {market_status['message']}")
            logger.warning(f"   Order will be placed but may not execute until market opens")

        # SAFETY CHECK: Get account to check mode (BEFORE any routing overrides)
        account = trading_accounts_collection.find_one({"account_id": account_id})
        mode = account.get('mode', 'paper_mock') if account else 'paper_mock'

        # CRITICAL SAFETY: Warning on live mode
        if mode == 'live':
            logger.critical(f"⚠️⚠️⚠️ LIVE MODE ORDER ⚠️⚠️⚠️")
            logger.critical(f"  Order ID: {order_data.get('order_id')}")
            logger.critical(f"  Instrument: {order_data.get('instrument')}")
            logger.critical(f"  Action: {order_data.get('action')}")
            logger.critical(f"  Quantity: {order_data.get('quantity')}")
            logger.critical(f"  Account: {account_id}")
            logger.critical(f"  ⚠️ REAL MONEY AT RISK ⚠️")

            # Check environment flag
            import os
            allow_live = os.getenv('ALLOW_LIVE_TRADING', 'false').lower() == 'true'
            if not allow_live:
                logger.error("❌ LIVE TRADING BLOCKED by ALLOW_LIVE_TRADING environment flag")
                logger.error("   Set ALLOW_LIVE_TRADING=true in .env to enable live trading")
                return {
                    "status": "REJECTED",
                    "reason": "Live trading not enabled. Set ALLOW_LIVE_TRADING=true in .env"
                }

        # MOCK MODE OVERRIDE: Route all orders to Mock_Paper if flag set
        if args.use_mock_broker:
            original_account = account_id
            account_id = 'Mock_Paper'
            logger.debug(f"MOCK MODE: Overriding account {original_account} → Mock_Paper")

        # Get broker instance for this account
        broker = get_broker_for_account(account_id)
        if not broker:
            logger.error(f"❌ No broker found for account {account_id} - order {order_data.get('order_id')} cannot be executed")
            return None

        # Ensure broker is connected
        if not broker.is_connected():
            logger.debug(f"Connecting to {broker.broker_name} for account {account_id}...")
            if not broker.connect():
                logger.error(f"❌ Failed to connect to {broker.broker_name} for {account_id}")
                return None

        logger.debug(f"Submitting order {order_data.get('order_id')} to {broker.broker_name} (account: {account_id})")

        # Use broker library's place_order method
        # The broker library handles all contract creation, qualification, and submission
        result = broker.place_order(order_data)

        if not result:
            logger.error(f"❌ Broker rejected order {order_data.get('order_id')}")
            return None

        # Track active orders for cancellation
        order_id = order_data['order_id']
        broker_order_id = result.get('broker_order_id')
        broker_confirmation_id = result.get('broker_confirmation_id')
        active_ibkr_orders[order_id] = broker_order_id

        # Log confirmation ID prominently
        logger.info(f"📋 Order {order_id} submitted to broker")
        logger.info(f"   Broker Order ID: {broker_order_id}")
        logger.info(f"   IBKR Confirmation ID: {broker_confirmation_id}")
        logger.info(f"   Status: {result.get('status')}")
        
        # Send Telegram notification for order placement
        telegram.notify_order_placed(
            order_id=order_id,
            symbol=order_data.get('instrument'),
            side=order_data.get('action', 'UNKNOWN'),
            quantity=order_data.get('quantity', 0),
            account=account_id,
            instrument_type=order_data.get('instrument_type', 'STOCK')
        )

        # Return result with fill data from broker (Mock broker fills instantly, real broker updates later)
        return {
            "order_id": order_data['order_id'],
            "ib_order_id": broker_order_id,
            "broker_confirmation_id": broker_confirmation_id,
            "status": result.get('status'),
            "filled": result.get('filled', 0),
            "remaining": result.get('remaining', order_data.get('quantity', 0)),
            "avg_fill_price": result.get('avg_fill_price', 0),
            "fills": result.get('fills', []),
            "num_legs": 1
        }

    except OrderRejectedError as e:
        logger.error(f"❌ Order {order_data.get('order_id')} rejected: {e.rejection_reason}")
        # Send Telegram notification for rejection
        telegram.notify_order_rejected(
            order_id=order_data.get('order_id'),
            symbol=order_data.get('instrument'),
            side=order_data.get('action', 'UNKNOWN'),
            quantity=order_data.get('quantity', 0),
            reason=e.rejection_reason,
            account=account_id
        )
        return None
    except InvalidSymbolError as e:
        logger.error(f"❌ Invalid symbol in order {order_data.get('order_id')}: {str(e)}")
        return None
    except BrokerAPIError as e:
        logger.error(f"❌ Broker API error for order {order_data.get('order_id')}: {e.error_code} - {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error submitting order {order_data.get('order_id')}: {str(e)}", exc_info=True)
        return None


# Pub/Sub removed - execution confirmations stored directly in MongoDB
# No need for separate publishing functions - all data in signal_store and trading_orders


def is_mock_broker(account_id: str) -> bool:
    """
    Check if account is a mock broker account.

    Mock brokers need manual balance updates when trades close with P&L.
    Real brokers handle this automatically and we fetch updated balances.
    """
    return 'MOCK' in account_id.upper() or account_id.startswith('Mock_')


def update_mock_broker_balance(
    account_id: str,
    realized_pnl: float,
    quantity_closed: float,
    exit_price: float
):
    """
    Update mock broker account balance after trade close.

    For mock brokers:
    - Add realized P&L to cash_balance
    - Reduce margin_used (position closed, capital freed)
    - Update equity

    Real brokers handle this automatically via their APIs.

    Args:
        account_id: Mock broker account ID
        realized_pnl: Net P&L from the trade (after commission)
        quantity_closed: Quantity that was closed
        exit_price: Exit price per unit
    """
    try:
        account = trading_accounts_collection.find_one({"account_id": account_id})
        if not account:
            logger.warning(f"⚠️ Account {account_id} not found for balance update")
            return

        # Current balances (nested under 'balances' object)
        balances = account.get('balances', {})
        current_cash = balances.get('cash_balance', account.get('cash_balance', 0.0))
        current_margin = balances.get('margin_used', account.get('margin_used', 0.0))
        current_equity = balances.get('equity', account.get('equity', 0.0))

        # Calculate updates
        # Add realized P&L to cash
        new_cash = current_cash + realized_pnl

        # Reduce margin (freed up capital from closed position)
        # Estimate margin as 10% of notional for futures/options
        freed_margin = (quantity_closed * exit_price) * 0.10
        new_margin = max(0.0, current_margin - freed_margin)

        # Update equity (cash + unrealized P&L + margin)
        new_equity = current_equity + realized_pnl

        # Update account document (balances are nested under 'balances')
        update_result = trading_accounts_collection.update_one(
            {"account_id": account_id},
            {
                "$set": {
                    "balances.cash_balance": new_cash,
                    "balances.cash": new_cash,
                    "balances.margin_used": new_margin,
                    "balances.equity": new_equity,
                    "balances.last_updated": datetime.utcnow()
                }
            }
        )

        if update_result.modified_count > 0:
            logger.info(
                f"✅ Updated mock broker {account_id} balance: "
                f"Cash: ${current_cash:.2f} → ${new_cash:.2f} "
                f"(+${realized_pnl:.2f} P&L), "
                f"Equity: ${current_equity:.2f} → ${new_equity:.2f}"
            )

            # IMMEDIATELY update fund total_equity (Single Source of Truth)
            fund_id = account.get('fund_id')
            if fund_id:
                update_fund_total_equity(fund_id)
        else:
            logger.warning(f"⚠️ No account balance updated for {account_id}")

    except Exception as e:
        logger.error(f"❌ Failed to update mock broker balance for {account_id}: {e}", exc_info=True)


def update_fund_total_equity(fund_id: str) -> float:
    """
    Update funds.total_equity by summing all account equities for this fund.

    THIS IS THE SINGLE SOURCE OF TRUTH for fund equity calculation.
    Called immediately after any account balance change in Execution Service.

    All other services (broker_poller, cerebro, dashboard) are READ-ONLY consumers.

    Args:
        fund_id: Fund ID to update

    Returns:
        Total equity across all accounts in the fund
    """
    try:
        if not fund_id:
            logger.warning("⚠️ No fund_id provided for equity update")
            return 0.0

        # Get all accounts for this fund
        accounts = list(trading_accounts_collection.find(
            {"fund_id": fund_id},
            {"balances.equity": 1, "account_id": 1}
        ))

        if not accounts:
            logger.warning(f"⚠️ No accounts found for fund {fund_id}")
            return 0.0

        # Sum equity across all accounts (from nested balances.equity)
        total_equity = sum(
            acc.get('balances', {}).get('equity', 0.0)
            for acc in accounts
        )

        # Get funds collection
        funds_collection = mongo_client['mathematricks_trading']['funds']

        # Update fund document with new total_equity
        update_result = funds_collection.update_one(
            {"fund_id": fund_id},
            {
                "$set": {
                    "total_equity": total_equity,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True  # Create if doesn't exist
        )

        if update_result.modified_count > 0 or update_result.upserted_id:
            logger.info(
                f"💰 Updated fund {fund_id} total_equity: ${total_equity:,.2f} "
                f"(from {len(accounts)} accounts)"
            )
        else:
            logger.debug(f"Fund {fund_id} total_equity unchanged: ${total_equity:,.2f}")

        return total_equity

    except Exception as e:
        logger.error(f"❌ Failed to update fund total_equity for {fund_id}: {e}", exc_info=True)
        return 0.0


def update_signal_store_with_execution(order_data: Dict[str, Any], execution_data: Dict[str, Any]):
    """
    Update signal_store with execution results and calculate PnL for EXIT signals.

    CONSOLIDATED SCHEMA (v3):
    - signal_store has ONE document per signal with legs[] array
    - Each leg has its own execution data: legs[i].execution
    - Position status calculated from ALL legs: position.status (PENDING → OPEN → PARTIAL → CLOSED)
    - All order details are stored in the leg (NO separate trading_orders collection)

    Args:
        order_data: Original order data from cerebro
        execution_data: Execution results (quantity_filled, avg_fill_price, fills, etc.)
    """
    try:
        from bson import ObjectId
        import sys
        import os
        
        # Add parent directory to path for imports
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from common.lag_calculator import calculate_processing_lag

        mathematricks_signal_id = order_data.get('mathematricks_signal_id')
        if not mathematricks_signal_id:
            logger.error(f"❌ No mathematricks_signal_id in order_data - cannot update signal_store | OrderID: {order_data.get('order_id')}")
            logger.error(f"   Order data keys: {list(order_data.keys())}")
            return

        logger.debug(f"Updating signal_store for mathematricks_signal_id: {mathematricks_signal_id}")

        # Use signal_type to determine ENTRY vs EXIT vs SCALE
        signal_type = order_data.get('signal_type') or 'ENTRY'
        signal_type = signal_type.upper()
        is_exit_or_scale_out = signal_type in ['EXIT', 'SCALE_OUT']
        signal_id = order_data.get('signal_id')  # Base signal ID for this leg

        # Get the parent signal document (CONSOLIDATED SCHEMA)
        signal_doc = signal_store_collection.find_one({"_id": ObjectId(mathematricks_signal_id)})
        if not signal_doc:
            logger.error(f"❌ Signal document {mathematricks_signal_id} not found")
            return

        # Find the leg matching this signal_id
        legs = signal_doc.get('legs', [])
        leg_index = None
        current_leg = None

        logger.debug(f"Looking for leg in signal document with {len(legs)} legs")
        logger.debug(f"Looking for signal_type={signal_type}, raw_signal_mongodb_id={order_data.get('raw_signal_mongodb_id')}")

        for idx, leg in enumerate(legs):
            logger.debug(f"Leg {idx}: leg_type={leg.get('leg_type')}, raw._id={leg.get('raw', {}).get('_id')}")

            if leg.get('raw', {}).get('_id') == order_data.get('raw_signal_mongodb_id'):
                leg_index = idx
                current_leg = leg
                logger.debug(f"✅ Matched leg by raw._id at index {idx}")
                break
            # Fallback: match by leg_type if we can't find by _id
            if leg_index is None and leg.get('leg_type') == signal_type:
                if signal_type == 'ENTRY' or (is_exit_or_scale_out and idx > 0):
                    leg_index = idx
                    current_leg = leg
                    logger.debug(f"✅ Matched leg by leg_type at index {idx}")
                    break

        if leg_index is None:
            logger.error(f"❌ Could not find leg for signal_type={signal_type} in signal document")
            logger.error(f"   Signal doc has {len(legs)} legs:")
            for idx, leg in enumerate(legs):
                logger.error(f"   Leg {idx}: type={leg.get('leg_type')}, leg_id={leg.get('leg_id')}")
            return

        # Build order document
        now = datetime.utcnow()
        order_doc = {
            "order_id": order_data.get('order_id'),
            "broker_order_id": execution_data.get('broker_order_id'),
            "fund_id": order_data.get('fund_id'),
            "account_id": order_data.get('account_id'),
            "quantity_requested": order_data.get('quantity', 0),
            "quantity_filled": execution_data['quantity_filled'],
            "avg_fill_price": execution_data['avg_fill_price'],
            "filled_at": now,
            "fills": execution_data.get('fills', [])
        }

        # Build/update execution for this leg
        existing_leg_execution = current_leg.get('execution')
        if existing_leg_execution and existing_leg_execution.get('orders'):
            # Append to existing orders
            existing_orders = existing_leg_execution.get('orders', [])
            existing_orders.append(order_doc)
            total_filled = sum(o.get('quantity_filled', 0) for o in existing_orders)
            total_value = sum(o.get('quantity_filled', 0) * o.get('avg_fill_price', 0) for o in existing_orders)
            weighted_avg = total_value / total_filled if total_filled > 0 else 0

            leg_execution = {
                "status": "FILLED",
                "orders": existing_orders,
                "total_quantity_filled": total_filled,
                "weighted_avg_price": weighted_avg,
                "total_cost_basis": total_value if not is_exit_or_scale_out else None,
                "total_proceeds": total_value if is_exit_or_scale_out else None
            }
        else:
            # First order for this leg
            total_value = execution_data['quantity_filled'] * execution_data['avg_fill_price']
            leg_execution = {
                "status": "FILLED",
                "orders": [order_doc],
                "total_quantity_filled": execution_data['quantity_filled'],
                "weighted_avg_price": execution_data['avg_fill_price'],
                "total_cost_basis": total_value if not is_exit_or_scale_out else None,
                "total_proceeds": total_value if is_exit_or_scale_out else None
            }
        
        # Update timestamps for execution
        updated_timestamps = current_leg.get('processing_timestamps', {})
        if not updated_timestamps.get('execution_started'):
            updated_timestamps['execution_started'] = now
        updated_timestamps['execution_completed'] = now
        
        # Calculate processing lag
        processing_lag = calculate_processing_lag(updated_timestamps)

        # Update the specific leg's execution using positional operator
        signal_store_collection.update_one(
            {
                "_id": ObjectId(mathematricks_signal_id),
                f"legs.{leg_index}.leg_id": current_leg['leg_id']
            },
            {
                "$set": {
                    f"legs.{leg_index}.execution": leg_execution,
                    f"legs.{leg_index}.processing_timestamps": updated_timestamps,
                    f"legs.{leg_index}.processing_lag": processing_lag,
                    "updated_at": now
                }
            }
        )

        logger.debug(f"✅ Updated leg {leg_index} ({signal_type}) with execution data")

        # Now calculate position status based on ALL legs
        # Refresh the document to get updated legs
        signal_doc = signal_store_collection.find_one({"_id": ObjectId(mathematricks_signal_id)})
        legs = signal_doc.get('legs', [])

        # Find ENTRY leg and calculate quantities
        entry_leg = next((leg for leg in legs if leg.get('leg_type') == 'ENTRY'), None)
        if not entry_leg or not entry_leg.get('execution'):
            logger.warning(f"⚠️ ENTRY leg not yet executed, skipping position status update")
            return

        entry_execution = entry_leg['execution']
        entry_quantity = entry_execution.get('total_quantity_filled', 0)
        entry_price = entry_execution.get('weighted_avg_price', 0)
        entry_cost_basis = entry_execution.get('total_cost_basis', entry_price * entry_quantity)

        # Get entry filled_at
        entry_filled_at = entry_execution['orders'][0].get('filled_at') if entry_execution.get('orders') else None
        holding_seconds = (datetime.utcnow() - entry_filled_at).total_seconds() if entry_filled_at else 0

        # Calculate total exit quantity from ALL exit/scale_out legs
        total_exit_quantity = 0
        cumulative_gross_pnl = 0
        cumulative_net_pnl = 0
        cumulative_commission = 0

        exit_legs = [leg for leg in legs if leg.get('leg_type') in ['EXIT', 'SCALE_OUT']]
        for exit_leg in exit_legs:
            if exit_leg.get('execution'):
                exit_exec = exit_leg['execution']
                exit_qty = exit_exec.get('total_quantity_filled', 0)
                exit_price_leg = exit_exec.get('weighted_avg_price', 0)

                total_exit_quantity += exit_qty

                # Calculate P&L for this exit leg
                gross_pnl = (exit_price_leg - entry_price) * exit_qty
                commission = sum(o.get('commission', 0) for o in exit_exec.get('orders', []))
                net_pnl = gross_pnl - commission

                cumulative_gross_pnl += gross_pnl
                cumulative_net_pnl += net_pnl
                cumulative_commission += commission

        # Determine position status
        remaining_quantity = entry_quantity - total_exit_quantity
        partial_exit_count = len(exit_legs)

        if total_exit_quantity >= entry_quantity:
            # Position fully closed
            position_status = "CLOSED"
            cumulative_pnl_percent = (cumulative_net_pnl / entry_cost_basis) * 100 if entry_cost_basis > 0 else 0

            cumulative_pnl_data = {
                "gross": cumulative_gross_pnl,
                "net": cumulative_net_pnl,
                "percent": cumulative_pnl_percent,
                "commission": cumulative_commission,
                "holding_seconds": holding_seconds
            }

            # Update position status
            signal_store_collection.update_one(
                {"_id": ObjectId(mathematricks_signal_id)},
                {
                    "$set": {
                        "position.status": "CLOSED",
                        "position.closed_at": datetime.utcnow(),
                        "position.pnl": cumulative_pnl_data,
                        "position.partial_exit_count": partial_exit_count,
                        "position.remaining_quantity": 0,
                        "position.entry_quantity": entry_quantity,
                        "position.exit_quantity": total_exit_quantity,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.debug(f"✅ Position CLOSED: {partial_exit_count} exits, {total_exit_quantity}/{entry_quantity}, P&L: ${cumulative_net_pnl:.2f}")

        elif total_exit_quantity > 0:
            # Partial exit
            position_status = "PARTIAL"
            cumulative_pnl_percent = (cumulative_net_pnl / entry_cost_basis) * 100 if entry_cost_basis > 0 else 0

            cumulative_pnl_data = {
                "gross": cumulative_gross_pnl,
                "net": cumulative_net_pnl,
                "percent": cumulative_pnl_percent,
                "commission": cumulative_commission,
                "holding_seconds": holding_seconds
            }

            # Update position status
            signal_store_collection.update_one(
                {"_id": ObjectId(mathematricks_signal_id)},
                {
                    "$set": {
                        "position.status": "PARTIAL",
                        "position.pnl": cumulative_pnl_data,
                        "position.partial_exit_count": partial_exit_count,
                        "position.remaining_quantity": remaining_quantity,
                        "position.entry_quantity": entry_quantity,
                        "position.exit_quantity": total_exit_quantity,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.debug(f"✅ Position PARTIAL: {partial_exit_count} exits, {total_exit_quantity}/{entry_quantity} exited, {remaining_quantity} remaining, P&L: ${cumulative_net_pnl:.2f}")

        else:
            # Only ENTRY executed, no exits yet
            position_status = "OPEN"

            signal_store_collection.update_one(
                {"_id": ObjectId(mathematricks_signal_id)},
                {
                    "$set": {
                        "position.status": "OPEN",
                        "position.opened_at": entry_filled_at or datetime.utcnow(),
                        "position.entry_quantity": entry_quantity,
                        "position.exit_quantity": 0,
                        "position.remaining_quantity": entry_quantity,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.debug(f"✅ Position OPEN: Entry executed with {entry_quantity} quantity")

        # Update mock broker balance if this was an exit
        if is_exit_or_scale_out and cumulative_net_pnl != 0:
            account_id = order_data.get('account_id')
            if account_id and is_mock_broker(account_id):
                # Get THIS account's specific order data from the exit leg
                current_exit_leg = legs[leg_index]
                if current_exit_leg.get('execution'):
                    # Find the specific order for this account (not total leg quantity)
                    account_order = None
                    for order in current_exit_leg['execution'].get('orders', []):
                        if order.get('account_id') == account_id:
                            account_order = order
                            break

                    if account_order:
                        this_exit_qty = account_order.get('quantity_filled', 0)
                        this_exit_price = account_order.get('avg_fill_price', 0)

                        # Find THIS account's entry price from the ENTRY leg
                        account_entry_price = entry_price  # Default to consolidated price
                        if entry_leg and entry_leg.get('execution'):
                            for entry_order in entry_leg['execution'].get('orders', []):
                                if entry_order.get('account_id') == account_id:
                                    account_entry_price = entry_order.get('avg_fill_price', entry_price)
                                    break

                        this_exit_pnl = (this_exit_price - account_entry_price) * this_exit_qty
                        update_mock_broker_balance(account_id, this_exit_pnl, this_exit_qty, this_exit_price)

    except Exception as e:
        logger.error(f"❌ Error updating signal_store with execution: {e}", exc_info=True)


def create_or_update_position(order_data: Dict[str, Any], filled_qty: float, avg_fill_price: float):
    """
    Create or update position in trading_accounts.{account_id}.open_positions after order fill
    Handles both ENTRY (create/increase) and EXIT (decrease/close) actions
    """
    try:
        strategy_id = order_data.get('strategy_id')
        instrument = order_data.get('instrument')
        direction = (order_data.get('direction') or 'LONG').upper()
        action = (order_data.get('action') or 'ENTRY').upper()
        signal_type = (order_data.get('signal_type') or '').upper()
        order_id = order_data.get('order_id')

        # Get account_id from order_data, with fallback based on broker mode
        default_account = "Mock_Paper" if args.use_mock_broker else "IBKR_Main"
        account_id = order_data.get('account_id', default_account)

        # Find account document
        account_doc = trading_accounts_collection.find_one({"account_id": account_id})
        if not account_doc:
            # Create account document if it doesn't exist
            account_doc = {
                "account_id": account_id,
                "open_positions": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            trading_accounts_collection.insert_one(account_doc)

        # Find existing position in open_positions array
        existing_position = None
        position_index = None
        open_positions = account_doc.get('open_positions', [])

        for idx, pos in enumerate(open_positions):
            if (pos.get('strategy_id') == strategy_id and
                pos.get('instrument') == instrument and
                pos.get('status') == 'OPEN'):
                existing_position = pos
                position_index = idx
                break

        # Determine if this is ENTRY or EXIT using signal_type OR direction+action
        # signal_type is preferred (set by Cerebro), fallback to direction+action logic
        is_entry = (
            signal_type == 'ENTRY' or
            (not signal_type and direction == 'LONG' and action == 'BUY') or
            (not signal_type and direction == 'SHORT' and action == 'SELL')
        )

        if is_entry:
            # ENTRY: Create new position or add to existing
            if existing_position:
                # Add to existing position (scale-in)
                current_qty = existing_position['quantity']
                current_avg_price = existing_position['avg_entry_price']

                new_qty = current_qty + filled_qty
                # Calculate new weighted average price
                new_avg_price = ((current_qty * current_avg_price) + (filled_qty * avg_fill_price)) / new_qty

                # Update the position in the array using array index
                trading_accounts_collection.update_one(
                    {'account_id': account_id},
                    {'$set': {
                        f'open_positions.{position_index}.quantity': new_qty,
                        f'open_positions.{position_index}.avg_entry_price': new_avg_price,
                        f'open_positions.{position_index}.updated_at': datetime.utcnow(),
                        f'open_positions.{position_index}.last_order_id': order_id
                    }}
                )
                logger.info(f"✅ Updated position {strategy_id}/{instrument}: {current_qty} → {new_qty} shares @ ${new_avg_price:.2f}")
            else:
                # Create new position and add to array
                position = {
                    'strategy_id': strategy_id,
                    'instrument': instrument,
                    'direction': direction,
                    'quantity': filled_qty,
                    'avg_entry_price': avg_fill_price,
                    'current_price': avg_fill_price,
                    'unrealized_pnl': 0.0,
                    'status': 'OPEN',
                    'entry_order_id': order_id,
                    'last_order_id': order_id,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                trading_accounts_collection.update_one(
                    {'account_id': account_id},
                    {'$push': {'open_positions': position}}
                )
                logger.info(f"✅ Created position {strategy_id}/{instrument}: {filled_qty} shares @ ${avg_fill_price:.2f}")

        else:
            # EXIT: Reduce or close position
            if existing_position:
                current_qty = existing_position['quantity']

                if filled_qty >= current_qty:
                    # Full exit - remove position from open_positions array
                    trading_accounts_collection.update_one(
                        {'account_id': account_id},
                        {'$pull': {
                            'open_positions': {
                                'strategy_id': strategy_id,
                                'instrument': instrument,
                                'status': 'OPEN'
                            }
                        }}
                    )
                    logger.info(f"✅ Closed position {strategy_id}/{instrument}: {current_qty} shares @ ${avg_fill_price:.2f}")
                else:
                    # Partial exit - reduce position quantity in array
                    new_qty = current_qty - filled_qty
                    trading_accounts_collection.update_one(
                        {'account_id': account_id},
                        {'$set': {
                            f'open_positions.{position_index}.quantity': new_qty,
                            f'open_positions.{position_index}.updated_at': datetime.utcnow(),
                            f'open_positions.{position_index}.last_order_id': order_id
                        }}
                    )
                    logger.info(f"✅ Reduced position {strategy_id}/{instrument}: {current_qty} → {new_qty} shares")
            else:
                logger.warning(f"⚠️ EXIT order {order_id} filled but no open position found for {strategy_id}/{instrument}")

    except Exception as e:
        logger.error(f"❌ Error creating/updating position: {e}", exc_info=True)


def get_account_state(account_id: str = None) -> Dict[str, Any]:
    """
    Get current account state using broker pool architecture.

    Args:
        account_id: Optional account ID. If not provided, gets state for all accounts.

    Returns:
        Dictionary with account balance, positions, and other state data.
    """
    try:
        if account_id:
            # Get state for specific account
            broker = get_broker_for_account(account_id)
            if not broker:
                logger.warning(f"No broker found for account {account_id}")
                return {}

            if not broker.is_connected():
                logger.warning(f"Broker for account {account_id} not connected")
                return {}

            balance = broker.get_account_balance(account_id)
            positions = broker.get_positions(account_id)

            return {
                "account_id": account_id,
                "balance": balance,
                "positions": positions,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Get state for all accounts in broker pool
            all_states = {}
            for acc_id, broker in broker_pool.items():
                if broker.is_connected():
                    balance = broker.get_account_balance(acc_id)
                    positions = broker.get_positions(acc_id)
                    all_states[acc_id] = {
                        "balance": balance,
                        "positions": positions
                    }
            return {
                "accounts": all_states,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"Error getting account state: {e}", exc_info=True)
        return {}


def cancel_order(order_id: str) -> bool:
    """
    Cancel an active order by order_id using broker library
    Returns True if successfully cancelled, False otherwise
    """
    try:
        # Look up the order in MongoDB to get account and broker_order_id
        order_doc = trading_orders_collection.find_one({'order_id': order_id})
        if not order_doc:
            logger.error(f"❌ Cannot cancel order {order_id} - not found in trading_orders")
            return False

        account_id = order_doc.get('account')
        if not account_id:
            logger.error(f"❌ Cannot cancel order {order_id} - no account specified")
            return False

        # Get broker_order_id from in-memory tracking or MongoDB
        if order_id in active_ibkr_orders:
            broker_order_id = active_ibkr_orders[order_id]
            logger.info(f"🚫 Cancelling order {order_id} (broker order ID: {broker_order_id} from memory)...")
        else:
            # Fall back to MongoDB for orders from previous sessions
            broker_order_id = order_doc.get('broker_order_id') or order_doc.get('ib_order_id')
            if not broker_order_id:
                logger.error(f"❌ Cannot cancel order {order_id} - no broker_order_id found in MongoDB")
                return False
            logger.info(f"🚫 Cancelling order {order_id} (broker order ID: {broker_order_id} from MongoDB)...")

        # Get broker from pool
        broker = get_broker_for_account(account_id)
        if not broker:
            logger.error(f"❌ Cannot cancel order {order_id} - broker not found for account {account_id}")
            return False

        # Use broker library to cancel order
        success = broker.cancel_order(broker_order_id)

        if success:
            # Remove from tracking if present
            if order_id in active_ibkr_orders:
                del active_ibkr_orders[order_id]
            logger.info(f"✅ Order {order_id} cancelled successfully")
            return True
        else:
            logger.warning(f"⚠️ Failed to cancel order {order_id}")
            return False

    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}", exc_info=True)
        return False


# Change Stream watcher removed - orders now received via HTTP API
# (Direct API call from cerebro after creating order)


def process_order_from_queue(order_item: Dict[str, Any]):
    """
    Process a single order from the queue in the main thread
    This runs in the main thread where IBKR's event loop is available
    """
    order_data = order_item['order_data']
    order_id = order_data.get('order_id')

    # Extract signal ID from order ID (format: {signal_id}_ORD)
    signal_id = order_id.replace('_ORD', '') if order_id.endswith('_ORD') else order_id

    try:
        logger.debug(f"Processing order from queue: {order_id}")

        # 🚨 CRITICAL FAILSAFE: Check if signal already processed
        if signal_id in processed_signal_ids:
            logger.critical(f"🚨 DUPLICATE SIGNAL BLOCKED! Signal {signal_id} already processed - REJECTING to prevent duplicate execution!")
            signal_logger.critical(f"ORDER: {signal_id} | DUPLICATE_BLOCKED | This signal was already processed - order rejected for safety")
            # No ack needed - MongoDB Change Stream handles this automatically
            return

        # Add to processed set
        processed_signal_ids.add(signal_id)
        logger.debug(f"Signal {signal_id} marked as processed (total tracked: {len(processed_signal_ids)})")

        # Log to signal_processing.log - Order received (concise)
        logger.info("-" * 50)
        logger.info(f"📥 ORDER RECEIVED: {order_data.get('instrument')} | {order_data.get('direction')} | Qty: {order_data.get('quantity')} | OrderID: {order_id}")
        signal_logger.info(f"ORDER: {signal_id} | ORDER_RECEIVED | OrderID={order_id} | Instrument={order_data.get('instrument')} | Direction={order_data.get('direction')} | Quantity={order_data.get('quantity')}")

        # Log open positions BEFORE order execution
        default_account = "Mock_Paper" if args.use_mock_broker else "IBKR_Main"
        account_id = order_data.get('account_id', default_account)
        log_open_positions(account_id, "BEFORE ORDER")

        # Submit order to broker (now safe - we're in main thread)
        logger.debug(f"Submitting order {order_id} to broker...")
        result = submit_order_to_broker(order_data)

        if result:
            # CRITICAL: Only create execution confirmation if order was actually FILLED or PARTIALLY FILLED
            # Do NOT create fake fills for orders that are just submitted/pending

            status = result.get('status', '')
            filled_qty = result.get('filled', 0)
            ib_order_id = result.get('ib_order_id')
            avg_fill_price = result.get('avg_fill_price', 0)

            logger.debug(f"Order {order_id} result: status={status}, filled={filled_qty}")

            # Only proceed if there was an actual fill
            if status in ['Filled', 'PartiallyFilled'] or filled_qty > 0:

                # Create execution confirmation
                execution = {
                    "order_id": order_id,
                    "execution_id": result.get('ib_order_id'),
                    "timestamp": datetime.utcnow(),
                    "account": "IBKR_Main",
                    "instrument": order_data.get('instrument'),
                    "side": "BUY" if order_data.get('direction') == 'LONG' else "SELL",
                    "quantity": filled_qty,
                    "price": result.get('avg_fill_price', 0),
                    "commission": 0,  # Would get from IBKR execution details
                    "status": "FILLED" if result.get('remaining', 0) == 0 else "PARTIAL_FILL",
                    "broker_response": result
                }

                # Note: Execution data is stored in signal_store.execution field
                # (redundant execution_confirmations collection and Pub/Sub removed)

                # Create or update position in open_positions collection
                logger.debug(f"Creating/updating position for {order_id}")
                create_or_update_position(order_data, filled_qty, avg_fill_price)

                # Log open positions AFTER order execution
                log_open_positions(account_id, "AFTER ORDER")

                # Update signal_store with execution data and calculate PnL
                # Calculate total commission from fills
                total_commission = sum(fill.get('commission', 0) for fill in result.get('fills', []))
                
                execution_data = {
                    "broker_order_id": result.get('ib_order_id'),
                    "quantity_filled": filled_qty,
                    "avg_fill_price": avg_fill_price,
                    "fills": result.get('fills', []),
                    "commission": total_commission
                }
                logger.info(f"💰 Commission for {order_id}: ${total_commission:.2f}")
                logger.debug(f"Updating signal_store for {order_id}")
                update_signal_store_with_execution(order_data, execution_data)

                # NOTE: trading_orders collection removed - all order data now in signal_store

                signal_logger.info(f"ORDER: {signal_id} | EXECUTION_CONFIRMED | Fill confirmed and saved to signal_store")
                logger.info(f"✅ ORDER COMPLETED: {order_data.get('instrument')} | Filled: {filled_qty} @ ${avg_fill_price:.2f} | Status: {execution['status']}")
                
                # Send Telegram notification for filled order
                telegram.notify_order_filled(
                    order_id=order_id,
                    symbol=order_data.get('instrument'),
                    side=order_data.get('action', 'UNKNOWN'),
                    quantity=filled_qty,
                    avg_fill_price=avg_fill_price,
                    commission=total_commission,
                    account=order_data.get('account')
                )
            else:
                # Order submitted but not filled yet - just log status
                signal_logger.info(f"ORDER: {signal_id} | WAITING_FOR_FILL | Order accepted by broker, waiting for execution...")
                logger.info(f"📋 Order {order_id} submitted to broker, status: {status}")
                # NOTE: trading_orders collection removed - status tracked in signal_store
        else:
            # Order failed
            signal_logger.error(f"ORDER: {signal_id} | ORDER_REJECTED | Broker rejected the order - check execution_service.log for details")
            logger.error(f"❌ Order {order_id} failed to execute")

            # NOTE: trading_orders collection removed - rejection tracked in signal_store

            # For exit orders, this is critical - implement retry logic
            if order_data.get('action') == 'EXIT':
                signal_logger.critical(f"ORDER: {signal_id} | EXIT_ORDER_FAILED | CRITICAL: Exit order failed - manual intervention required!")
                logger.critical(f"🚨 EXIT order {order_id} FAILED - manual intervention required!")
                logger.critical(f"   Symbol: {order_data.get('instrument')}")
                logger.critical(f"   Quantity: {order_data.get('quantity')}")
                logger.critical(f"   Account: {order_data.get('account')}")
                logger.critical(f"   ⚠️  POSITION MAY STILL BE OPEN - CHECK MANUALLY ⚠️")
                # TODO Phase 1.5: Send Telegram alert (will be implemented next)

        logger.debug(f"Completed processing order {order_id}")

    except Exception as e:
        logger.error(f"Error processing order {order_id}: {str(e)}", exc_info=True)
        # Order will remain in PENDING state and can be manually retried if needed


# MongoDB Change Stream watchers replace Pub/Sub subscribers
# (watch_trading_orders function defined above)


def periodic_account_updates():
    """
    Publish account updates periodically (every 30 seconds)
    """
    while True:
        try:
            time.sleep(30)
            # TODO: Update get_account_state() to work with broker pool
            # account_state = get_account_state()
            # if account_state:
            #     publish_account_update(account_state)
        except Exception as e:
            logger.error(f"Error in periodic account updates: {str(e)}")


if __name__ == "__main__":
    logger.info("🚀 Execution Service Starting")
    
    # Start FastAPI health check server in background thread
    fastapi_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    fastapi_thread.start()
    logger.info("✅ Health check server started on port 8083")

    # Connect to all brokers in pool (continue even if some fail - orders will route to available brokers)
    if not connect_all_brokers():
        logger.warning("⚠️  No brokers connected - orders will queue until brokers available")
    else:
        logger.info(f"✅ Broker pool: {len(broker_pool)} broker(s) ready")
        service_status['broker_pool_size'] = len(broker_pool)
        service_status['brokers_connected'] = len(broker_pool)

    # Initialize Mock broker with empty positions
    if args.use_mock_broker:
        account_id = "Mock_Paper"
        trading_accounts_collection.update_one(
            {'account_id': account_id},
            {
                '$set': {
                    'open_positions': [],
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        logger.info(f"✅ Mock broker account '{account_id}' initialized with empty positions")

    service_status['pending_orders_processed'] = 0  # No longer checking for pending orders in trading_orders
    
    # Change Stream watcher removed - orders now received via HTTP API
    # (Direct API call from cerebro after creating order)
    
    # Mark service as ready
    service_status['ready'] = True
    logger.info("✅ Execution Service ready - listening for orders via HTTP API")
    logger.info("*" * 50)
    try:
        while True:
            # Check if there are orders in the queue (non-blocking)
            try:
                order_item = order_queue.get(timeout=0.1)
                process_order_from_queue(order_item)
            except queue.Empty:
                pass

            # Small sleep to prevent CPU spinning
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Shutting down Execution Service")
        broker.disconnect()
