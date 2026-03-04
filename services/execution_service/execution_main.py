"""
Execution Service - Modern Architecture
Strategy-driven broker initialization and order execution
Consolidated service: handles broker connections, order execution, and account data
"""
import os
import sys
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set
from pymongo import MongoClient
from dotenv import load_dotenv
import time

# Add services to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'services'))

# Import broker library
from brokers import BrokerFactory
from services.utils.encryption import decrypt_dict

# Import API server
from services.execution_service import api

# Import gateway controller for IB Gateway management
from services.execution_service.gateway_controller import GatewayController

# Import account management (migrated from account-data-service)
from services.execution_service.repository import TradingAccountRepository
from services.execution_service.broker_poller import BrokerPoller

# Load environment
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Configure logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')
file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'execution_service.log'))
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27018')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']

# Global broker pool, gateway controller, and account repository
broker_pool: Dict[str, any] = {}
gateway_controller = GatewayController()
trading_accounts_collection = db['trading_accounts']
trading_accounts_repository = TradingAccountRepository(trading_accounts_collection)
broker_poller = None


def get_required_accounts_from_strategies() -> Set[str]:
    """
    Analyze all strategies to determine which accounts are needed.
    Returns set of account_ids that should be initialized.
    """
    logger.info("📊 Analyzing strategies to determine required accounts...")
    
    # Get all strategies from MongoDB
    strategies = list(db.strategies.find({}, {"strategy_id": 1, "accounts": 1, "_id": 0}))
    logger.info(f"Found {len(strategies)} strategies in database")
    
    # Collect all unique account_ids across all routing modes
    required_accounts = set()
    
    for strategy in strategies:
        strategy_id = strategy.get('strategy_id')
        accounts = strategy.get('accounts', {})
        
        # Add accounts from all routing modes (mock, paper, live)
        for mode, account_list in accounts.items():
            if account_list:  # Skip empty lists
                required_accounts.update(account_list)
                logger.debug(f"  {strategy_id} -> {mode}: {account_list}")
    
    logger.info(f"✅ Required accounts: {sorted(required_accounts)}")
    return required_accounts


def get_account_details(account_id: str) -> Optional[Dict]:
    """Fetch account details from MongoDB."""
    return db.trading_accounts.findOne({"account_id": account_id})


def decrypt_auth_details(auth_details: Dict, broker_name: str) -> Dict:
    """Decrypt authentication details based on broker type."""
    if not auth_details:
        return {}
    
    # Define which fields to decrypt per broker
    decrypt_fields_map = {
        'IBKR': ['password', 'username', 'totp_secret'],
        'Coinbase': ['api_key_name', 'api_key'],
        'Binance': ['api_key', 'api_secret'],
        'Bybit': ['api_key', 'api_secret'],
        'Alpaca': ['api_key', 'api_secret'],
        'Oanda': ['api_key'],
        'Mock': []
    }
    
    fields_to_decrypt = decrypt_fields_map.get(broker_name, [])
    
    if fields_to_decrypt:
        return decrypt_dict(auth_details, fields_to_decrypt)
    return auth_details


def build_broker_config(broker_name: str, account_id: str, auth_details: Dict) -> Dict:
    """Build broker configuration from account details."""
    config = {"broker": broker_name, "account_id": account_id}
    
    if broker_name == 'IBKR':
        config.update({
            "host": auth_details.get('host', 'host.docker.internal'),
            "port": auth_details.get('port', 4004),
            "client_id": auth_details.get('client_id', 100)
        })
        if 'market_data_type' in auth_details:
            config['market_data_type'] = auth_details['market_data_type']
    
    elif broker_name in ['Binance', 'Bybit']:
        config.update({
            "api_key": auth_details.get('api_key'),
            "api_secret": auth_details.get('api_secret'),
            "testnet": auth_details.get('testnet', False)
        })
    
    elif broker_name == 'Alpaca':
        config.update({
            "api_key": auth_details.get('api_key'),
            "api_secret": auth_details.get('api_secret'),
            "paper": auth_details.get('paper', True)
        })
    
    elif broker_name == 'Oanda':
        config.update({
            "api_key": auth_details.get('api_key'),
            "practice": auth_details.get('practice', True)
        })

    elif broker_name == 'Coinbase':
        config.update({
            "api_key": auth_details.get('api_key_name') or auth_details.get('api_key'),
            "api_secret": auth_details.get('api_key'),
            "sandbox": auth_details.get('sandbox', True)
        })
    
    elif broker_name == 'Mock':
        config.update(auth_details)
    
    else:
        config.update(auth_details)
    
    return config


def initialize_broker(account_id: str) -> Optional[any]:
    """
    Initialize a single broker for the given account.
    Returns broker instance or None if initialization failed.
    """
    try:
        # Get account from MongoDB
        account = db.trading_accounts.find_one({"account_id": account_id})
        
        if not account:
            logger.error(f"❌ Broker {account_id}: Account not found in database")
            return None
        
        broker_name = account.get('broker')
        auth_details = account.get('authentication_details', {})
        
        # Decrypt sensitive fields
        auth_details = decrypt_auth_details(auth_details, broker_name)
        
        # Build broker config
        config = build_broker_config(broker_name, account_id, auth_details)
        
        # Create broker instance
        broker = BrokerFactory.create_broker(config)
        
        logger.info(f"✅ Broker {account_id}: Started ({broker_name})")
        return broker
        
    except Exception as e:
        logger.error(f"❌ Broker {account_id}: Error: {str(e)}")
        return None


def connect_brokers():
    """Connect all initialized brokers."""
    logger.info("\n🔌 Connecting Brokers...")
    
    connected = 0
    for account_id, broker in broker_pool.items():
        try:
            if hasattr(broker, 'connect'):
                broker.connect()
                if broker.is_connected():
                    logger.info(f"✅ Connected: {account_id}")
                    connected += 1
                else:
                    logger.warning(f"⚠️  Failed to connect: {account_id}")
            else:
                logger.info(f"✅ No connection needed: {account_id}")
                connected += 1
        except Exception as e:
            logger.error(f"❌ Connection error for {account_id}: {e}")
    
    logger.info(f"\n✅ Connected: {connected}/{len(broker_pool)} brokers")


def start_ibkr_gateways():
    """
    Start IB Gateway containers for all IBKR accounts in the broker pool.
    This ensures IB Gateway is running before trying to connect brokers.
    """
    logger.info("\n🚀 Starting IB Gateway containers for IBKR accounts...")
    
    ibkr_accounts = []
    
    # Find all IBKR accounts in broker pool
    for account_id, broker in broker_pool.items():
        if hasattr(broker, 'broker_name') and broker.broker_name == 'IBKR':
            # Get account details from MongoDB
            account = db.trading_accounts.find_one({'account_id': account_id})
            if account:
                # CRITICAL: Decrypt auth details before passing to gateway controller
                auth_details = account.get('authentication_details', {})
                decrypted_auth = decrypt_auth_details(auth_details, 'IBKR')
                
                # Update account with decrypted auth
                account_copy = account.copy()
                account_copy['authentication_details'] = decrypted_auth
                
                ibkr_accounts.append(account_copy)
    
    if not ibkr_accounts:
        logger.info("No IBKR accounts found - skipping gateway startup")
        return
    
    logger.info(f"Found {len(ibkr_accounts)} IBKR account(s)")
    
    # Start gateway for each IBKR account
    for account in ibkr_accounts:
        account_id = account['account_id']
        try:
            success = gateway_controller.create_gateway_for_account(account)
            if success:
                logger.info(f"✅ IB Gateway ready for {account_id}")
                
                # Wait for gateway to fully initialize and log in (takes ~60s)
                logger.info(f"⏳ Waiting 60s for {account_id} gateway to fully log in...")
                time.sleep(60)
            else:
                logger.error(f"❌ Failed to start gateway for {account_id}")
        except Exception as e:
            logger.error(f"❌ Error starting gateway for {account_id}: {e}")
    
    logger.info("✅ IB Gateway startup complete")


def initialize_broker_pool():
    """Initialize all required brokers based on active strategies."""
    global broker_pool
    
    logger.info("🚀 Initializing Broker Pool")
    logger.info("=" * 80)
    
    # Step 1: Determine which accounts are needed
    required_accounts = get_required_accounts_from_strategies()
    
    if not required_accounts:
        logger.warning("⚠️  No accounts required - broker pool will be empty")
        return
    
    # Step 2: Initialize each broker
    logger.info(f"\n📦 Initializing {len(required_accounts)} broker(s)...")
    
    for account_id in sorted(required_accounts):
        broker = initialize_broker(account_id)
        if broker:
            broker_pool[account_id] = broker
    
    # Step 3: Start IB Gateway containers for IBKR accounts
    if broker_pool:
        start_ibkr_gateways()
    
    # Step 4: Connect brokers
    if broker_pool:
        connect_brokers()
    
    # Step 5: Summary
    logger.info(f"\n✅ Broker Pool Ready: {len(broker_pool)}/{len(required_accounts)} brokers initialized")
    logger.info("=" * 80)


def main():
    """Main execution service entry point."""
    global broker_poller
    
    logger.info("🚀 Execution Service Starting (Consolidated with Account Data)")
    logger.info("=" * 80)
    
    # Initialize broker pool
    initialize_broker_pool()
    
    # Start broker polling service (migrated from account-data-service)
    # CRITICAL: Pass broker_pool to prevent duplicate IBKR connections (competing sessions)
    logger.info("\n📊 Starting background broker polling...")
    broker_poller = BrokerPoller(
        repository=trading_accounts_repository,
        interval=300,  # Poll every 5 minutes
        mongodb_url=MONGODB_URI,
        mongodb_client=mongo_client,
        broker_pool=broker_pool  # Reuse execution_service's broker connections
    )
    broker_poller.start()
    logger.info("✅ Broker polling started (using shared broker pool)")
    
    # Start API server in background thread
    logger.info("\n🌐 Starting API Server...")
    api_thread = threading.Thread(
        target=api.run_api_server,
        args=(broker_pool, True, trading_accounts_repository),
        daemon=True
    )
    api_thread.start()
    
    # Keep service running
    logger.info("\n🎯 Execution Service Ready (with Account Management)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down Execution Service")
        
        # Stop broker poller
        if broker_poller:
            broker_poller.stop()
            logger.info("✅ Stopped broker polling")
        
        # Cleanup brokers
        for account_id, broker in broker_pool.items():
            try:
                if hasattr(broker, 'disconnect'):
                    broker.disconnect()
                    logger.info(f"✅ Disconnected: {account_id}")
            except Exception as e:
                logger.warning(f"⚠️  Error disconnecting {account_id}: {e}")


if __name__ == "__main__":
    main()
