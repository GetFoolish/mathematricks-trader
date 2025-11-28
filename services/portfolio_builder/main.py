#!/usr/bin/env python3
"""
PortfolioBuilder Service
Handles strategy management, portfolio optimization, and research workflows
Extracted from CerebroService for separation of concerns

Port: 8003
"""

import os
import sys
import logging
import subprocess
import shutil
import glob
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine project root dynamically
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # services/portfolio_builder
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # mathematricks-trader/
PYTHON_PATH = os.path.join(PROJECT_ROOT, 'venv', 'bin', 'python')
RESEARCH_OUTPUTS_DIR = os.path.join(SCRIPT_DIR, 'research', 'outputs')
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'portfolio_builder.log')

# Ensure directories exist
os.makedirs(RESEARCH_OUTPUTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('portfolio_builder')

# Initialize FastAPI
app = FastAPI(title="PortfolioBuilder Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    logger.error("MONGODB_URI not set in environment")
    sys.exit(1)

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']
signals_db = mongo_client['mathematricks_signals']  # Raw signals database

# Collections
strategies_collection = db['strategies']
current_allocation_collection = db['current_allocation']
portfolio_tests_collection = db['portfolio_tests']
incoming_signals_collection = signals_db['trading_signals']  # Raw signals from MongoDB Atlas
signal_store_collection = db['signal_store']  # Unified signal storage with embedded cerebro decisions
trading_orders_collection = db['trading_orders']

logger.info("=" * 80)
logger.info("PortfolioBuilder Service Starting")
logger.info("=" * 80)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "portfolio_builder",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Strategy Management APIs
# ============================================================================

@app.get("/api/v1/strategies")
async def get_all_strategies():
    """
    Get all strategy configurations from unified strategies collection
    Returns list of all strategies with metadata and backtest data
    """
    try:
        strategies = list(strategies_collection.find({}))

        # Remove MongoDB _id
        for strategy in strategies:
            strategy.pop('_id', None)

        return {
            "status": "success",
            "count": len(strategies),
            "strategies": strategies
        }

    except Exception as e:
        logger.error(f"Error fetching strategies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """
    Get single strategy configuration
    Includes backtest data (stored in same document in unified collection)
    """
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Remove MongoDB _id
        strategy.pop('_id', None)

        return {
            "status": "success",
            "strategy": strategy
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching strategy {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies")
async def create_strategy(strategy_data: Dict[str, Any]):
    """
    Create new strategy configuration in unified strategies collection
    Validates required fields and saves to MongoDB
    """
    try:
        # Validate required fields
        required_fields = ['strategy_id', 'name', 'asset_class', 'instruments']
        for field in required_fields:
            if field not in strategy_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        strategy_id = strategy_data['strategy_id']

        # Check if strategy already exists
        existing = strategies_collection.find_one({"strategy_id": strategy_id})
        if existing:
            raise HTTPException(status_code=409, detail=f"Strategy {strategy_id} already exists")

        # Add timestamps
        strategy_data['created_at'] = datetime.utcnow()
        strategy_data['updated_at'] = datetime.utcnow()
        strategy_data['status'] = strategy_data.get('status', 'ACTIVE')

        # Insert into MongoDB
        strategies_collection.insert_one(strategy_data)

        logger.info(f"✅ Created strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} created",
            "strategy_id": strategy_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating strategy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, updates: Dict[str, Any]):
    """
    Update strategy configuration in unified strategies collection
    Allows partial updates of strategy fields
    """
    try:
        # Check if strategy exists
        existing = strategies_collection.find_one({"strategy_id": strategy_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Add updated timestamp
        updates['updated_at'] = datetime.utcnow()

        # Update in MongoDB
        result = strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {"$set": updates}
        )

        if result.modified_count == 0:
            logger.warning(f"No changes made to strategy {strategy_id}")

        logger.info(f"✅ Updated strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} updated",
            "strategy_id": strategy_id,
            "modified_count": result.modified_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """
    Delete strategy configuration (hard delete)
    Permanently removes the strategy from MongoDB
    """
    try:
        # Check if strategy exists
        existing = strategies_collection.find_one({"strategy_id": strategy_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Hard delete - permanently remove from database
        result = strategies_collection.delete_one({"strategy_id": strategy_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete strategy {strategy_id}")

        logger.info(f"✅ Deleted (hard) strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} permanently deleted",
            "strategy_id": strategy_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting strategy {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies/{strategy_id}/sync-backtest")
async def sync_strategy_backtest(strategy_id: str, backtest_data: Dict[str, Any]):
    """
    Sync/update strategy backtest data in unified strategies collection
    Updates the backtest_data field within the same document
    """
    try:
        # Check if strategy exists
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Add updated timestamp to backtest data
        backtest_data['last_updated'] = datetime.utcnow()

        # Update backtest_data field in the unified document
        result = strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "backtest_data": backtest_data,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Synced backtest data for strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Backtest data synced for {strategy_id}",
            "strategy_id": strategy_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing backtest for {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies/{strategy_id}/refresh-cache")
async def refresh_strategy_cache(strategy_id: str):
    """
    Refresh strategy cache
    Placeholder for future cache invalidation logic
    """
    try:
        logger.info(f"Cache refresh requested for strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Cache refreshed for {strategy_id}",
            "strategy_id": strategy_id
        }

    except Exception as e:
        logger.error(f"Error refreshing cache for {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Portfolio Allocation APIs
# ============================================================================

@app.get("/api/v1/allocations/current")
async def get_current_allocation():
    """
    Get current active allocation
    Returns the single "approved" allocation that the system is currently using
    """
    try:
        allocation = current_allocation_collection.find_one({}, {'_id': 0})
        return {
            "status": "success",
            "allocation": allocation
        }
    except Exception as e:
        logger.error(f"Error fetching current allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/allocations/approve")
async def approve_allocation(request: Dict[str, Any]):
    """
    Approve allocation (makes it current)
    Replaces the current allocation with the approved one
    Also saves to local JSON cache for Cerebro to use
    """
    try:
        allocations = request.get('allocations')
        if not allocations:
            raise HTTPException(status_code=400, detail="allocations field is required")

        # Calculate total allocation (or use provided value)
        total_allocation_pct = sum(allocations.values())

        # Create new current allocation document
        new_allocation = {
            "allocations": allocations,
            "total_allocation_pct": total_allocation_pct,
            "approved_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "mode": "approved"
        }

        # Replace the current allocation (upsert - insert if doesn't exist)
        current_allocation_collection.delete_many({})  # Remove all existing
        current_allocation_collection.insert_one(new_allocation)

        # Save to local JSON cache for Cerebro
        cerebro_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'cerebro_service',
            'current_portfolio_allocation_approved.json'
        )

        cache_data = {
            "_comment": "Current approved portfolio allocation (cached from MongoDB)",
            "_source": "Frontend approval via PortfolioBuilder API",
            "_metadata": {
                "approved_at": new_allocation["approved_at"].isoformat(),
                "updated_at": new_allocation["updated_at"].isoformat(),
                "num_strategies": len(allocations)
            },
            "allocations": allocations,
            "total_allocation_pct": sum(allocations.values()),
            "mode": "approved_downloaded_from_mongo",
            "last_updated": datetime.utcnow().isoformat(),
            "update_action": "allocation_changed_by_user"
        }

        with open(cerebro_cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"✅ Approved new allocation with {len(allocations)} strategies")
        logger.info(f"✅ Saved to cache: {cerebro_cache_path}")

        return {
            "status": "success",
            "message": "Allocation approved and set as current"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Portfolio Testing / Research Lab APIs
# ============================================================================

@app.get("/api/v1/portfolio-tests")
async def get_portfolio_tests():
    """
    Get list of portfolio tests
    Returns all test runs sorted by creation date (newest first)
    """
    try:
        tests = list(portfolio_tests_collection.find({}, {'_id': 0}).sort('created_at', -1))

        # Sanitize data - replace NaN/Inf with 0.0 for JSON compatibility
        for test in tests:
            if 'allocations' in test:
                for strategy_id, value in test['allocations'].items():
                    if pd.isna(value) or not np.isfinite(value):
                        test['allocations'][strategy_id] = 0.0

            if 'performance' in test:
                for metric, value in test['performance'].items():
                    if pd.isna(value) or not np.isfinite(value):
                        test['performance'][metric] = 0.0

        return {
            "status": "success",
            "count": len(tests),
            "tests": tests
        }

    except Exception as e:
        logger.error(f"Error fetching portfolio tests: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/portfolio-tests/{test_id}")
async def delete_portfolio_test(test_id: str):
    """
    Delete a portfolio test
    """
    try:
        # Get test to find file paths
        test = portfolio_tests_collection.find_one({"test_id": test_id}, {'_id': 0})

        if not test:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

        # Delete archived files from research/outputs
        test_archive_dir = f"{RESEARCH_OUTPUTS_DIR}/{test_id}"

        if os.path.exists(test_archive_dir):
            shutil.rmtree(test_archive_dir)
            logger.info(f"Deleted test archive directory: {test_archive_dir}")

        # Delete from MongoDB
        result = portfolio_tests_collection.delete_one({"test_id": test_id})

        logger.info(f"✅ Deleted portfolio test: {test_id}")

        return {
            "status": "success",
            "message": f"Test {test_id} deleted"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting test {test_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio-tests/{test_id}/tearsheet")
async def get_tearsheet(test_id: str):
    """
    Get the HTML tearsheet for a specific test
    """
    try:
        # Get test from MongoDB
        test = portfolio_tests_collection.find_one({"test_id": test_id}, {'_id': 0})

        if not test:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

        # Get tearsheet file path
        tearsheet_path = test.get('files', {}).get('tearsheet_html')

        if not tearsheet_path or not os.path.exists(tearsheet_path):
            raise HTTPException(status_code=404, detail="Tearsheet not found for this test")

        return FileResponse(tearsheet_path, media_type="text/html")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tearsheet for {test_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/portfolio-tests/run")
async def run_portfolio_test(request: Dict[str, Any]):
    """
    Run a new portfolio optimization test (Research Lab)
    Runs construct_portfolio.py with selected strategies and saves results to MongoDB
    """
    try:
        strategies = request.get('strategies', [])
        constructor = request.get('constructor', 'max_hybrid')

        if not strategies or len(strategies) == 0:
            raise HTTPException(status_code=400, detail="At least one strategy must be selected")

        # Generate test ID
        test_id = f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"🔬 Running portfolio test: {test_id}")
        logger.info(f"   Constructor: {constructor}")
        logger.info(f"   Strategies: {strategies}")

        # Create output directory for this test in research/outputs
        test_output_dir = f"{RESEARCH_OUTPUTS_DIR}/{test_id}"
        os.makedirs(test_output_dir, exist_ok=True)

        # Run construct_portfolio.py with output directory set to test folder
        cmd = [
            PYTHON_PATH,
            f"{PROJECT_ROOT}/services/portfolio_builder/research/construct_portfolio.py",
            "--constructor", constructor,
            "--strategies", ",".join(strategies),
            "--output-dir", test_output_dir
        ]

        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.error(f"Portfolio construction failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Portfolio construction failed: {result.stderr}")

        logger.info(f"Portfolio construction output:\n{result.stdout}")

        # Files are already in the correct location - just need to find them
        allocation_files = glob.glob(f"{test_output_dir}/*_allocations.csv")
        equity_files = glob.glob(f"{test_output_dir}/*_equity.csv")
        correlation_files = glob.glob(f"{test_output_dir}/*_correlation.csv")
        tearsheet_files = glob.glob(f"{test_output_dir}/*_tearsheet.html")

        if not allocation_files:
            raise HTTPException(status_code=500, detail="No allocation file generated")

        # Get file paths
        archived_files = {
            'allocation_csv': allocation_files[0] if allocation_files else None,
            'equity_csv': equity_files[0] if equity_files else None,
            'correlation_csv': correlation_files[0] if correlation_files else None,
            'tearsheet_html': tearsheet_files[0] if tearsheet_files else None
        }

        logger.info(f"Test files saved to: {test_output_dir}")
        logger.info(f"Files: {list(archived_files.values())}")

        # Parse allocations from CSV (last row has final allocations)
        allocations_df = pd.read_csv(archived_files['allocation_csv'])

        # Get final window's allocation (last row)
        final_row = allocations_df.iloc[-1]
        allocations = {}
        for strategy_id in strategies:
            if strategy_id in allocations_df.columns:
                value = final_row[strategy_id]
                # Handle NaN/Inf values - replace with 0.0
                if pd.isna(value) or not np.isfinite(value):
                    allocations[strategy_id] = 0.0
                else:
                    allocations[strategy_id] = float(value)

        # Parse performance metrics from QuantStats tearsheet HTML
        performance_metrics = {}
        if 'tearsheet_html' in archived_files and archived_files['tearsheet_html'] and os.path.exists(archived_files['tearsheet_html']):
            with open(archived_files['tearsheet_html'], 'r') as f:
                html_content = f.read()

            # Extract metrics using regex patterns
            cagr_match = re.search(r'CAGR[^<]*</td>\s*<td[^>]*>([-\d.]+)%', html_content)
            sharpe_match = re.search(r'<td[^>]*>Sharpe</td>\s*<td[^>]*>([-\d.]+)</td>', html_content)
            max_dd_match = re.search(r'<td[^>]*>Max Drawdown</td>\s*<td[^>]*>([-\d.]+)%', html_content)
            volatility_match = re.search(r'<td[^>]*>Volatility \(ann\.\)</td>\s*<td[^>]*>([-\d.]+)%', html_content)

            performance_metrics = {
                "cagr": float(cagr_match.group(1)) if cagr_match else 0.0,
                "sharpe": float(sharpe_match.group(1)) if sharpe_match else 0.0,
                "max_drawdown": float(max_dd_match.group(1)) if max_dd_match else 0.0,
                "volatility": float(volatility_match.group(1)) if volatility_match else 0.0
            }

            logger.info(f"Performance metrics from tearsheet: {performance_metrics}")
        else:
            logger.warning("No tearsheet HTML file found - cannot extract performance metrics")

        # Save test record to MongoDB
        test_record = {
            "test_id": test_id,
            "constructor": constructor,
            "strategies": strategies,
            "allocations": allocations,
            "performance": performance_metrics,
            "files": archived_files,
            "created_at": datetime.utcnow(),
            "status": "completed"
        }

        portfolio_tests_collection.insert_one(test_record)

        logger.info(f"✅ Portfolio test {test_id} saved to MongoDB")

        return {
            "status": "success",
            "test_id": test_id,
            "allocations": allocations,
            "performance": performance_metrics,
            "files": archived_files
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running portfolio test: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Activity Tab APIs (Read-Only)
# ============================================================================

def serialize_mongo_document(doc):
    """Recursively convert MongoDB document to JSON-serializable format"""
    from bson import ObjectId

    if isinstance(doc, dict):
        return {k: serialize_mongo_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_mongo_document(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc

@app.get("/api/v1/activity/signals")
async def get_recent_signals(limit: int = 50, environment: str = None):
    """Get recent signals from signal_store - filtered by environment if specified"""
    try:
        query = {}
        if environment:
            query['environment'] = environment

        # Query signal_store - serialize all documents to handle ObjectIds and datetimes
        signal_store_docs = list(signal_store_collection.find(query).sort('received_at', -1).limit(limit))

        # Serialize all documents to handle ObjectIds and datetimes
        signal_store_docs = [serialize_mongo_document(doc) for doc in signal_store_docs]

        # Format signals for frontend
        signals = []
        for doc in signal_store_docs:
            signal_data = doc.get('signal_data', {})
            signal_details = signal_data.get('signal', {})

            # Handle both single-leg and multi-leg signals
            if isinstance(signal_details, list) and len(signal_details) > 0:
                signal_details = signal_details[0]  # Use first leg for display

            # Extract cerebro decision and remove any _id fields
            cerebro_decision = doc.get('cerebro_decision')
            decision_status = None
            if cerebro_decision:
                # Remove _id from cerebro_decision if present
                if isinstance(cerebro_decision, dict) and '_id' in cerebro_decision:
                    cerebro_decision.pop('_id', None)
                decision_status = cerebro_decision.get('decision', 'PENDING')

            formatted_signal = {
                'signal_id': doc.get('signal_id') or signal_data.get('signalID') or signal_data.get('signal_id'),
                'strategy_id': signal_data.get('strategy_name', 'Unknown'),
                'timestamp': doc.get('received_at'),
                'created_at': doc.get('received_at'),
                'instrument': signal_details.get('ticker') or signal_details.get('instrument'),
                'action': signal_details.get('action'),
                'direction': signal_details.get('direction'),
                'price': signal_details.get('price') or signal_details.get('entry_price'),
                'quantity': signal_details.get('quantity'),
                'environment': doc.get('environment', 'production'),
                'processed_by_cerebro': cerebro_decision is not None,
                'receive_lag_ms': doc.get('receive_lag_ms', 0),
                'cerebro_decision': cerebro_decision,
                'decision_status': decision_status
            }
            signals.append(formatted_signal)

        return {"status": "success", "count": len(signals), "signals": signals}
    except Exception as e:
        logger.error(f"Error fetching signals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/activity/orders")
async def get_recent_orders(limit: int = 50, environment: str = None):
    """Get recent orders - filtered by environment if specified"""
    try:
        query = {}
        if environment:
            query['environment'] = environment

        orders = list(trading_orders_collection.find(query, {'_id': 0}).sort('timestamp', -1).limit(limit))
        return {"status": "success", "count": len(orders), "orders": orders}
    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/activity/decisions")
async def get_cerebro_decisions(limit: int = 50, environment: str = None):
    """Get recent Cerebro decisions from signal_store (embedded decisions)"""
    try:
        query = {
            'cerebro_decision': {'$ne': None}  # Only get signals with decisions
        }
        if environment:
            query['environment'] = environment

        # Query signal_store and extract embedded decisions
        signal_store_docs = list(signal_store_collection.find(query, {'_id': 0}).sort('received_at', -1).limit(limit))

        # Extract decisions from signal_store documents
        decisions = []
        for doc in signal_store_docs:
            decision = doc.get('cerebro_decision', {})
            if decision:
                # Add signal_id from signal_data for consistency with old format
                signal_data = doc.get('signal_data', {})
                decision['signal_id'] = doc.get('signal_id') or signal_data.get('signalID') or signal_data.get('signal_id')
                decisions.append(decision)

        return {"status": "success", "count": len(decisions), "decisions": decisions}
    except Exception as e:
        logger.error(f"Error fetching decisions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting PortfolioBuilder Service on port 8003")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
