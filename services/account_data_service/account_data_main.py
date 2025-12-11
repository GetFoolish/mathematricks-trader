"""
Account Data Service - Simplified v2.0
Manages trading accounts with real-time balance and position data
Single responsibility: Account state management only
"""
import os
import sys
import logging
import math
import json
from datetime import datetime
from typing import Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import uvicorn


class NaNSafeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles NaN and Inf values"""
    def encode(self, o):
        return super().encode(self._sanitize(o))

    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return 0.0
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj


def sanitize_response(data: Any) -> Any:
    """Recursively sanitize data to replace NaN/Inf with 0"""
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return 0.0
        return data
    elif isinstance(data, dict):
        return {k: sanitize_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_response(item) for item in data]
    return data

# Add parent directory to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, PROJECT_ROOT)

from services.account_data_service.config import (
    MONGODB_URI,
    DATABASE_NAME,
    PORT,
    POLL_INTERVAL_SECONDS,
    LOG_LEVEL
)
from services.account_data_service.repository import TradingAccountRepository
from services.account_data_service.broker_poller import BrokerPoller
from services.account_data_service.models import CreateAccountRequest, MarginPreviewRequest
from brokers import BrokerFactory

# Configure logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Create custom formatter matching Cerebro format
custom_formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')

# Create file handler with custom format
file_handler = logging.FileHandler(os.path.join(LOG_DIR, 'account_data_service.log'))
file_handler.setFormatter(custom_formatter)

# Create console handler with same format
console_handler = logging.StreamHandler()
console_handler.setFormatter(custom_formatter)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Account Data Service",
    version="2.0-simplified",
    description="Simplified account management service"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
mongo_client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
    tlsAllowInvalidCertificates=True  # For development
)
db = mongo_client[DATABASE_NAME]
trading_accounts_collection = db['trading_accounts']

# Initialize repository and poller
repository = TradingAccountRepository(trading_accounts_collection)
poller = BrokerPoller(repository, interval=POLL_INTERVAL_SECONDS, mongodb_url=MONGODB_URI)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test MongoDB connection
        mongo_client.server_info()
        return {
            "status": "healthy",
            "service": "account_data_service",
            "version": "2.0-simplified",
            "mongodb": "connected",
            "poller_running": poller.running
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "account_data_service",
            "version": "2.0-simplified",
            "error": str(e)
        }


# ============================================================================
# ACCOUNT MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/v1/accounts")
def create_account(request: CreateAccountRequest):
    """
    Create new trading account

    Example request body:
    {
      "account_id": "IBKR_Main",
      "account_name": "IBKR Main Account",
      "broker": "IBKR",
      "account_number": "U1234567",
      "authentication_details": {
        "auth_type": "TWS",
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 100
      }
    }
    """
    try:
        # Check if account already exists
        existing = repository.get_account(request.account_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Account {request.account_id} already exists"
            )

        # Create account document
        account_doc = {
            "_id": request.account_id,
            "account_name": request.account_name,
            "account_id": request.account_id,
            "broker": request.broker,
            "account_number": request.account_number,
            "authentication_details": request.authentication_details.dict(),
            "balances": {
                "base_currency": "USD",
                "equity": 0,
                "cash_balance": 0,
                "margin_used": 0,
                "margin_available": 0,
                "unrealized_pnl": 0,
                "realized_pnl": 0,
                "margin_utilization_pct": 0,
                "last_updated": datetime.utcnow()
            },
            "open_positions": [],
            "positions_last_updated": datetime.utcnow(),
            "connection_status": "DISCONNECTED",
            "last_poll_time": None,
            "last_poll_success": False,
            "status": "ACTIVE",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        repository.create_account(account_doc)

        logger.info(f"✅ Created account: {request.account_id}")

        return {
            "status": "created",
            "account_id": request.account_id,
            "message": f"Account {request.account_id} created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/accounts")
def list_accounts(broker: Optional[str] = None, status: str = "ACTIVE"):
    """
    List all trading accounts

    Query params:
    - broker: Filter by broker (e.g., "IBKR", "Zerodha")
    - status: Filter by status (default: "ACTIVE")
    """
    try:
        accounts = repository.list_accounts(broker=broker, status=status)
        # Sanitize response to handle NaN/Inf values from MongoDB
        response_data = {
            "accounts": accounts,
            "count": len(accounts)
        }
        return sanitize_response(response_data)
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/accounts/{account_id}")
def get_account(account_id: str):
    """Get single account details"""
    try:
        account = repository.get_account(account_id)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_id} not found"
            )
        return sanitize_response({"account": account})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/accounts/{account_id}/sync")
def sync_account(account_id: str):
    """
    Force immediate account sync (poll now)
    Triggers broker polling for this specific account
    """
    try:
        account = repository.get_account(account_id)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_id} not found"
            )

        # Poll this account immediately
        logger.info(f"Forcing sync for {account_id}")
        poller.poll_account(account)

        # Get updated account
        updated_account = repository.get_account(account_id)

        return {
            "status": "synced",
            "account_id": account_id,
            "timestamp": datetime.utcnow(),
            "connection_status": updated_account['connection_status'],
            "equity": updated_account['balances']['equity'],
            "num_positions": len(updated_account['open_positions'])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/accounts/{account_id}")
def delete_account(account_id: str):
    """
    Soft delete account (set status to INACTIVE)
    Account will no longer be polled
    """
    try:
        account = repository.get_account(account_id)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_id} not found"
            )

        repository.delete_account(account_id)

        logger.info(f"🗑️  Deleted account: {account_id}")

        return {
            "status": "deleted",
            "account_id": account_id,
            "message": f"Account {account_id} set to INACTIVE"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BACKWARD COMPATIBILITY ENDPOINTS (for CerebroService)
# ============================================================================

@app.get("/api/v1/account/{account_name}/state")
def get_account_state_legacy(account_name: str):
    """
    LEGACY: Get account state (backward compatible with old format)
    Used by CerebroService - DO NOT REMOVE
    """
    try:
        account = repository.get_account(account_name)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_name} not found"
            )

        # Transform to old format expected by CerebroService
        state = {
            "account_id": account['account_id'],
            "account": account['account_id'],
            "broker_id": account['broker'],
            "timestamp": account['balances']['last_updated'],
            "equity": account['balances']['equity'],
            "cash_balance": account['balances']['cash_balance'],
            "margin_used": account['balances']['margin_used'],
            "margin_available": account['balances']['margin_available'],
            "unrealized_pnl": account['balances']['unrealized_pnl'],
            "realized_pnl": account['balances']['realized_pnl'],
            "open_positions": account['open_positions'],
            "open_orders": [],  # Not tracking orders in this service
            "created_at": account['updated_at']
        }

        return {"state": state}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting legacy account state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/account/{account_name}/margin")
def get_account_margin_legacy(account_name: str):
    """
    LEGACY: Get margin info
    Used by CerebroService - DO NOT REMOVE
    """
    try:
        account = repository.get_account(account_name)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_name} not found"
            )

        return {
            "margin_available": account['balances']['margin_available'],
            "margin_used": account['balances']['margin_used'],
            "margin_utilization_pct": account['balances']['margin_utilization_pct'],
            "equity": account['balances']['equity']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting margin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/account/{account_name}/sync")
def sync_account_legacy(account_name: str):
    """
    LEGACY: Force account sync (backward compatible)
    Redirects to new endpoint
    """
    return sync_account(account_name)


@app.post("/api/v1/account/{account_name}/margin-preview")
def get_margin_preview(account_name: str, request: MarginPreviewRequest):
    """
    Get margin requirements for a hypothetical order using IBKR's whatIfOrder API.

    This queries the actual broker for real margin requirements before placing an order.
    Currently only supports IBKR accounts.

    Example request body:
    {
        "instrument": "GC",
        "direction": "LONG",
        "quantity": 2,
        "order_type": "MARKET",
        "instrument_type": "FUTURE",
        "expiry": "20250224",
        "exchange": "COMEX"
    }

    Returns margin impact data from broker.
    """
    import concurrent.futures
    import asyncio

    try:
        account = repository.get_account(account_name)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_name} not found"
            )

        # Currently only IBKR supports whatIfOrder
        if account['broker'] != 'IBKR':
            raise HTTPException(
                status_code=400,
                detail=f"Margin preview only supported for IBKR accounts, not {account['broker']}"
            )

        # Build broker config
        # IBKR connection settings come from environment variables (IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID)
        config = {
            "broker": "IBKR",
            "account_id": account_name,
        }

        # Build order for margin query
        order = {
            "instrument": request.instrument,
            "direction": request.direction,
            "quantity": request.quantity,
            "order_type": request.order_type,
            "instrument_type": request.instrument_type,
        }

        # Add optional fields
        if request.expiry:
            order["expiry"] = request.expiry
        if request.exchange:
            order["exchange"] = request.exchange
        if request.limit_price:
            order["limit_price"] = request.limit_price

        logger.info(f"Getting margin preview for {account_name}: {request.instrument} {request.direction} {request.quantity}")

        # Run margin query in separate thread (IBKR needs its own event loop)
        def query_margin():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                broker = BrokerFactory.create_broker(config)

                if not broker.is_connected():
                    if not broker.connect():
                        raise Exception("Failed to connect to IBKR")

                # Query margin impact
                result = broker.get_order_margin_impact(order)

                # Disconnect
                broker.disconnect()

                return result
            finally:
                loop.close()

        # Execute in thread pool with timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(query_margin)
            try:
                result = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                raise HTTPException(
                    status_code=504,
                    detail="Timeout waiting for margin data from IBKR"
                )

        return {
            "account_id": account_name,
            "instrument": request.instrument,
            "quantity": request.quantity,
            "direction": request.direction,
            "margin_impact": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting margin preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FUND-LEVEL AGGREGATION
# ============================================================================

@app.get("/api/v1/fund/state")
def get_fund_state():
    """
    Calculate fund state on-the-fly from all active accounts
    No separate collection needed
    """
    try:
        accounts = repository.list_accounts(status="ACTIVE")

        # Calculate aggregates
        total_equity = sum(acc['balances']['equity'] for acc in accounts)
        total_cash = sum(acc['balances']['cash_balance'] for acc in accounts)
        total_margin_used = sum(acc['balances']['margin_used'] for acc in accounts)
        total_margin_available = sum(acc['balances']['margin_available'] for acc in accounts)
        total_unrealized_pnl = sum(acc['balances']['unrealized_pnl'] for acc in accounts)
        total_realized_pnl = sum(acc['balances']['realized_pnl'] for acc in accounts)

        margin_utilization_pct = (
            (total_margin_used / total_equity * 100) if total_equity > 0 else 0
        )

        # Group by broker
        broker_breakdown = {}
        for acc in accounts:
            broker = acc['broker']
            if broker not in broker_breakdown:
                broker_breakdown[broker] = {
                    "broker_id": broker,
                    "equity": 0,
                    "cash": 0,
                    "num_accounts": 0,
                    "accounts": []
                }
            broker_breakdown[broker]['equity'] += acc['balances']['equity']
            broker_breakdown[broker]['cash'] += acc['balances']['cash_balance']
            broker_breakdown[broker]['num_accounts'] += 1
            broker_breakdown[broker]['accounts'].append(acc['account_id'])

        response_data = {
            "fund_state": {
                "timestamp": datetime.utcnow(),
                "total_equity": total_equity,
                "total_cash": total_cash,
                "total_margin_used": total_margin_used,
                "total_margin_available": total_margin_available,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_realized_pnl": total_realized_pnl,
                "margin_utilization_pct": margin_utilization_pct,
                "num_accounts": len(accounts),
                "broker_breakdown": list(broker_breakdown.values())
            }
        }
        return sanitize_response(response_data)

    except Exception as e:
        logger.error(f"Error calculating fund state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
def startup():
    """Service startup"""
    logger.info("=" * 70)
    logger.info("Starting Account Data Service v2.0 (Simplified)")
    logger.info("=" * 70)
    logger.info(f"MongoDB URI: {MONGODB_URI}")
    logger.info(f"Database: {DATABASE_NAME}")
    logger.info(f"Poll interval: {POLL_INTERVAL_SECONDS}s")
    logger.info(f"Port: {PORT}")
    logger.info("=" * 70)

    # Test MongoDB connection
    try:
        mongo_client.server_info()
        logger.info("✅ MongoDB connected")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise

    # Start broker polling
    poller.start()

    # Count accounts
    num_accounts = len(repository.list_accounts(status="ACTIVE"))
    logger.info(f"📊 {num_accounts} active accounts configured")

    logger.info("✅ Service started successfully")


@app.on_event("shutdown")
def shutdown():
    """Service shutdown"""
    logger.info("Shutting down Account Data Service...")

    # Stop poller
    poller.stop()

    # Close MongoDB
    mongo_client.close()

    logger.info("✅ Service shut down cleanly")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower()
    )
