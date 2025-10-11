"""
Account Data Service - MVP
Centralizes and reconciles real-time account state from brokers.
Provides REST API for CerebroService to query account/margin status.
"""
import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/account_data_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Account Data Service", version="1.0.0-MVP")

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(
    mongo_uri,
    tls=True,
    tlsAllowInvalidCertificates=True  # For development only
)
db = mongo_client['mathematricks_trading']
account_state_collection = db['account_state']
execution_confirmations_collection = db['execution_confirmations']

# In-memory cache of current account state
account_state_cache: Dict[str, Dict[str, Any]] = {}

# Initialize Google Cloud Pub/Sub Subscriber
project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
subscriber = pubsub_v1.SubscriberClient()
execution_confirmations_subscription = subscriber.subscription_path(project_id, 'execution-confirmations-sub')
account_updates_subscription = subscriber.subscription_path(project_id, 'account-updates-sub')


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "account_data_service", "version": "1.0.0-MVP"}


@app.get("/api/v1/account/{account_name}/state")
async def get_account_state(account_name: str):
    """
    Get current account state (equity, margin, positions)
    Used by CerebroService for position sizing decisions
    """
    try:
        # Check cache first
        if account_name in account_state_cache:
            return {"account": account_name, "state": account_state_cache[account_name]}

        # Fallback to database
        latest_state = account_state_collection.find_one(
            {"account": account_name},
            sort=[("timestamp", -1)]
        )

        if not latest_state:
            raise HTTPException(status_code=404, detail=f"Account {account_name} not found")

        # Remove MongoDB _id for JSON serialization
        latest_state.pop('_id', None)

        return {"account": account_name, "state": latest_state}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching account state for {account_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/account/{account_name}/margin")
async def get_account_margin(account_name: str):
    """
    Get margin availability for account
    Simplified endpoint for quick margin checks
    """
    try:
        account_state = await get_account_state(account_name)
        state = account_state['state']

        return {
            "account": account_name,
            "equity": state.get('equity', 0),
            "margin_used": state.get('margin_used', 0),
            "margin_available": state.get('margin_available', 0),
            "margin_utilization_pct": (state.get('margin_used', 0) / state.get('equity', 1)) * 100 if state.get('equity', 0) > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error fetching margin for {account_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/account/{account_name}/sync")
async def sync_account_with_broker(account_name: str):
    """
    Force sync account state with broker
    Called on startup or when reconciliation is needed
    """
    try:
        logger.info(f"Syncing account {account_name} with broker")

        # TODO: Call broker API to fetch full account state
        # For MVP, this is a placeholder
        # Will integrate with ExecutionService or direct broker API

        return {
            "status": "success",
            "message": f"Account {account_name} sync initiated",
            "account": account_name
        }

    except Exception as e:
        logger.error(f"Error syncing account {account_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def execution_confirmations_callback(message):
    """
    Callback for execution confirmations from Pub/Sub
    Updates account state based on fills
    """
    try:
        data = json.loads(message.data.decode('utf-8'))
        logger.info(f"Received execution confirmation: {data}")

        # Store execution confirmation
        execution_confirmations_collection.insert_one({
            **data,
            "created_at": datetime.utcnow()
        })

        # Update account state based on execution
        update_account_state_from_execution(data)

        message.ack()

    except Exception as e:
        logger.error(f"Error processing execution confirmation: {str(e)}", exc_info=True)
        message.nack()


def account_updates_callback(message):
    """
    Callback for account updates from Pub/Sub
    Updates account state from broker data
    """
    try:
        data = json.loads(message.data.decode('utf-8'))
        logger.info(f"Received account update for {data.get('account')}")

        account_name = data.get('account')

        # Store in database
        account_state_collection.insert_one({
            **data,
            "timestamp": datetime.utcnow(),
            "created_at": datetime.utcnow()
        })

        # Update cache
        account_state_cache[account_name] = data

        message.ack()

    except Exception as e:
        logger.error(f"Error processing account update: {str(e)}", exc_info=True)
        message.nack()


def update_account_state_from_execution(execution_data: Dict[str, Any]):
    """
    Update account state based on execution confirmation
    This is a simplified MVP implementation
    """
    account_name = execution_data.get('account')

    if account_name in account_state_cache:
        # Update cache (simplified logic)
        logger.info(f"Updating account state for {account_name} based on execution")

        # In full implementation, would:
        # 1. Update open_positions array
        # 2. Recalculate margin_used
        # 3. Update unrealized_pnl
        # 4. Update cash_balance

        # For MVP, we rely on periodic account updates from broker


def start_pubsub_subscribers():
    """
    Start Pub/Sub subscribers in background threads
    """
    def start_execution_confirmations_sub():
        streaming_pull_future = subscriber.subscribe(
            execution_confirmations_subscription,
            callback=execution_confirmations_callback
        )
        logger.info("Listening for execution confirmations...")
        streaming_pull_future.result()

    def start_account_updates_sub():
        streaming_pull_future = subscriber.subscribe(
            account_updates_subscription,
            callback=account_updates_callback
        )
        logger.info("Listening for account updates...")
        streaming_pull_future.result()

    # Start subscribers in background threads
    threading.Thread(target=start_execution_confirmations_sub, daemon=True).start()
    threading.Thread(target=start_account_updates_sub, daemon=True).start()


@app.on_event("startup")
async def startup_event():
    """
    On startup, sync with broker state and start Pub/Sub listeners
    """
    logger.info("Account Data Service starting up...")

    # Start Pub/Sub subscribers
    start_pubsub_subscribers()

    # TODO: Sync all configured accounts with brokers
    # This is critical for ensuring state consistency
    logger.info("Account Data Service ready")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Account Data Service MVP")
    uvicorn.run(app, host="0.0.0.0", port=8002)
