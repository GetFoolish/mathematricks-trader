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
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from dotenv import load_dotenv
import uuid
import hashlib

# Load environment variables
load_dotenv()

# Import backtest processing modules
from backtest_upload_handler import (
    parse_csv,
    normalize_returns,
    generate_synthetic_columns,
    merge_backtest_data,
    calculate_backtest_hash,
    invalidate_allocations_for_strategy,
    BacktestUploadError
)
from metrics_calculator import calculate_all_metrics

# Import tearsheet generator directly to avoid circular imports
import quantstats as qs

# Determine project root dynamically
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # services/portfolio_builder
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # mathematricks-trader/

# Determine Python executable dynamically (works in both Docker and local environments)
# In Docker: /usr/local/bin/python
# On host: /path/to/.venv/bin/python
# Use 'python3' as fallback to find Python in PATH
PYTHON_PATH = sys.executable if os.path.exists(sys.executable) else 'python3'

RESEARCH_OUTPUTS_DIR = os.path.join(SCRIPT_DIR, 'research', 'outputs')
SUBMISSIONS_TEARSHEETS_DIR = os.path.join(SCRIPT_DIR, 'submissions_tearsheets')
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'portfolio_builder.log')

# Ensure directories exist
os.makedirs(RESEARCH_OUTPUTS_DIR, exist_ok=True)
os.makedirs(SUBMISSIONS_TEARSHEETS_DIR, exist_ok=True)
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
# Try MONGODB_URI_LOCAL first (for local dev), fallback to MONGODB_URI (for Docker)
MONGODB_URI = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI')
if not MONGODB_URI:
    logger.error("Neither MONGODB_URI_LOCAL nor MONGODB_URI set in environment")
    sys.exit(1)

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']
signals_db = mongo_client['mathematricks_signals']  # Raw signals database

# Collections
strategies_collection = db['strategies']
uploaded_strategies_collection = db['uploaded_strategies']  # Public strategy submissions
current_allocation_collection = db['current_allocation']
portfolio_tests_collection = db['portfolio_tests']
portfolio_allocations_collection = db['portfolio_allocations']  # For hash tracking and invalidation
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
# Public Strategy Submission APIs (No Auth Required)
# ============================================================================

@app.post("/api/v1/public/submit-strategy")
async def submit_strategy_public(
    file: UploadFile = File(...),
    strategy_name: str = Form(...),
    developer_name: str = Form(...),
    developer_email: str = Form(...),
    developer_note: str = Form(""),
    starting_capital: float = Form(1000000.0)
):
    """
    PUBLIC ENDPOINT: Submit strategy backtest data for review

    No authentication required - this is for external strategy developers

    Form Data:
    - file: CSV file with backtest data
    - strategy_name: Name of the strategy
    - developer_name: Developer's full name
    - developer_email: Developer's email address
    - developer_note: Optional description/notes about the strategy
    - starting_capital: Starting capital for synthetic data (default: 1M)

    Returns:
    - submission_id: Unique ID for tracking this submission
    - metrics: Calculated performance metrics (CAGR, Sharpe, Calmar, etc.)
    - equity_curve: Daily equity values for charting
    - warnings: Any warnings about synthetic data generation
    - synthetic_columns: List of columns that were generated synthetically
    """
    try:
        logger.info(f"📥 Public strategy submission: {strategy_name} from {developer_name}")

        # Generate unique submission ID
        submission_id = f"sub_{uuid.uuid4().hex[:12]}"

        # Read CSV file
        file_content = await file.read()

        # Parse CSV
        df = parse_csv(file_content)
        logger.info(f"   Parsed CSV: {len(df)} rows, columns: {list(df.columns)}")

        # Normalize returns (handle percentage formats)
        df = normalize_returns(df)

        # Generate synthetic columns if missing
        df, synthetic_columns = generate_synthetic_columns(df, starting_capital=starting_capital)

        # Convert DataFrame to list of dicts for MongoDB
        # Use lowercase field names to match existing approved strategies
        raw_data_backtest_full = []
        for _, row in df.iterrows():
            raw_data_backtest_full.append({
                'date': row['Date'].isoformat() if hasattr(row['Date'], 'isoformat') else str(row['Date']),
                'return': float(row['Daily_Return_Pct']) / 100.0,  # Convert percentage to decimal (2.5% -> 0.025)
                'pnl': float(row.get('Daily_PnL', 0)),
                'margin_used': float(row.get('Max_Margin_Used', 0)),
                'notional_value': float(row.get('Max_Notional_Value', 0)),
                'account_equity': float(row.get('Account_Equity', starting_capital))
            })

        # Calculate performance metrics
        metrics = calculate_all_metrics(raw_data_backtest_full)
        logger.info(f"   Metrics: CAGR={metrics['cagr']:.2f}%, Sharpe={metrics['sharpe_ratio']:.2f}, Calmar={metrics['calmar_ratio']:.2f}")

        # Build equity curve for frontend charting
        equity_curve = [
            {"date": data['date'], "equity": data['account_equity']}
            for data in raw_data_backtest_full
        ]

        # Build warnings list
        warnings = []
        if synthetic_columns:
            warnings.append(f"Generated synthetic data for columns: {', '.join(synthetic_columns)}")
            warnings.append("For more accurate optimization, consider providing real data for these columns.")

        # Create submission document
        submission_doc = {
            "submission_id": submission_id,
            "status": "PENDING_APPROVAL",

            # Strategy metadata (will be used when approved)
            "strategy_name": strategy_name,

            # Developer information
            "developer_info": {
                "name": developer_name,
                "email": developer_email,
                "note": developer_note
            },

            # Backtest data
            "raw_data_backtest_full": raw_data_backtest_full,

            # Calculated metrics
            "metrics": metrics,

            # Synthetic data tracking
            "synthetic_data": {
                "columns_generated": synthetic_columns,
                "starting_capital": starting_capital
            },

            # Timestamps
            "submitted_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Insert into MongoDB
        uploaded_strategies_collection.insert_one(submission_doc)

        logger.info(f"✅ Strategy submission saved: {submission_id}")

        # Generate tearsheet asynchronously (don't block the response)
        tearsheet_path = os.path.join(SUBMISSIONS_TEARSHEETS_DIR, f"{submission_id}.html")
        try:
            # Convert data to pandas Series for tearsheet
            returns_df = pd.DataFrame(raw_data_backtest_full)
            returns_df['Date'] = pd.to_datetime(returns_df['Date'])
            returns_df = returns_df.set_index('Date')
            returns_series = returns_df['Daily_Return_Pct'] / 100  # Convert percentage to decimal

            # Generate tearsheet using QuantStats
            qs.reports.html(
                returns_series,
                benchmark=None,
                output=tearsheet_path,
                title=f"{strategy_name} - Performance Tearsheet",
                download_filename=tearsheet_path
            )

            # Update submission with tearsheet path
            uploaded_strategies_collection.update_one(
                {"submission_id": submission_id},
                {"$set": {"tearsheet_path": tearsheet_path, "tearsheet_generated": True}}
            )
            logger.info(f"📊 Tearsheet generated: {tearsheet_path}")
        except Exception as e:
            logger.error(f"Failed to generate tearsheet for {submission_id}: {str(e)}", exc_info=True)
            # Update submission to mark tearsheet generation failed
            uploaded_strategies_collection.update_one(
                {"submission_id": submission_id},
                {"$set": {"tearsheet_generated": False, "tearsheet_error": str(e)}}
            )

        return {
            "status": "success",
            "submission_id": submission_id,
            "message": "Strategy submitted successfully and is now pending approval",
            "metrics": metrics,
            "equity_curve": equity_curve,
            "warnings": warnings,
            "synthetic_columns": synthetic_columns
        }

    except BacktestUploadError as e:
        logger.error(f"Backtest upload validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing strategy submission: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/v1/public/submission/{submission_id}")
async def get_submission_status(submission_id: str):
    """
    PUBLIC ENDPOINT: Check status of a strategy submission

    No authentication required - allows developers to check their submission status

    Returns:
    - Full submission details including status, metrics, and review information
    """
    try:
        submission = uploaded_strategies_collection.find_one(
            {"submission_id": submission_id},
            {'_id': 0}  # Exclude MongoDB ObjectId
        )

        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

        return {
            "status": "success",
            "submission": submission
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching submission {submission_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/public/submission/{submission_id}/tearsheet")
async def get_submission_tearsheet(submission_id: str):
    """
    PUBLIC ENDPOINT: Get the HTML tearsheet for a strategy submission
    """
    try:
        # Get submission from MongoDB
        submission = uploaded_strategies_collection.find_one({"submission_id": submission_id}, {'_id': 0})

        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

        # Check if tearsheet was generated
        if not submission.get('tearsheet_generated'):
            raise HTTPException(status_code=404, detail="Tearsheet not yet generated or generation failed")

        # Get tearsheet file path
        tearsheet_path = submission.get('tearsheet_path')

        if not tearsheet_path or not os.path.exists(tearsheet_path):
            raise HTTPException(status_code=404, detail="Tearsheet file not found")

        return FileResponse(tearsheet_path, media_type="text/html")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tearsheet for {submission_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Admin Strategy Submission Management APIs (Auth Required)
# ============================================================================

@app.get("/api/v1/admin/submissions")
async def get_all_submissions(status: Optional[str] = None):
    """
    ADMIN ENDPOINT: Get all strategy submissions

    Query params:
    - status: Filter by status (PENDING_APPROVAL, APPROVED, REJECTED, or ALL)

    Returns list of all submissions sorted by submission date (newest first)
    """
    try:
        # Build query
        query = {}
        if status and status.upper() != 'ALL':
            query['status'] = status.upper()

        # Fetch submissions
        submissions = list(
            uploaded_strategies_collection.find(query, {'_id': 0})
            .sort('submitted_at', -1)
        )

        return {
            "status": "success",
            "count": len(submissions),
            "submissions": submissions
        }

    except Exception as e:
        logger.error(f"Error fetching submissions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/admin/submissions/{submission_id}/approve")
async def approve_submission(submission_id: str, approval_data: Dict[str, Any]):
    """
    ADMIN ENDPOINT: Approve a strategy submission and add to active strategies

    Request body:
    {
        "strategy_id": "SPX_NewStrategy",  # Required: unique strategy ID
        "asset_class": "equity",           # Required
        "instruments": ["SPX", "SPY"],     # Required
        "accounts": ["IBKR_Main"],         # Optional: accounts to assign
        "status": "ACTIVE",                # Optional: ACTIVE or TESTING
        "trading_mode": "PAPER",           # Optional: PAPER or LIVE
        "include_in_optimization": true,   # Optional
        "notes": "Approved by John"        # Optional
    }

    Logic:
    1. Fetch submission from uploaded_strategies
    2. Calculate backtest data hash
    3. Create strategy document in strategies collection
    4. Update submission status to APPROVED
    """
    try:
        # Fetch submission
        submission = uploaded_strategies_collection.find_one({"submission_id": submission_id})

        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

        if submission['status'] != 'PENDING_APPROVAL':
            raise HTTPException(
                status_code=400,
                detail=f"Submission is already {submission['status']}"
            )

        # Extract approval data
        strategy_id = approval_data.get('strategy_id')
        if not strategy_id:
            raise HTTPException(status_code=400, detail="strategy_id is required")

        # Check if strategy_id already exists
        existing_strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if existing_strategy:
            raise HTTPException(
                status_code=409,
                detail=f"Strategy {strategy_id} already exists. Choose a different strategy_id."
            )

        asset_class = approval_data.get('asset_class')
        if not asset_class:
            raise HTTPException(status_code=400, detail="asset_class is required")

        instruments = approval_data.get('instruments', [])
        if not instruments:
            raise HTTPException(status_code=400, detail="instruments is required")

        # Calculate backtest data hash
        backtest_hash = calculate_backtest_hash(submission['raw_data_backtest_full'])

        # Convert backtest data from capitalized to lowercase for construct_portfolio.py compatibility
        raw_data_lowercase = []
        for item in submission['raw_data_backtest_full']:
            raw_data_lowercase.append({
                'date': item['Date'],
                'return': float(item['Daily_Return_Pct']) / 100.0,  # Convert % to decimal
                'pnl': float(item.get('Daily_PnL', 0)),
                'margin_used': float(item.get('Max_Margin_Used', 0)),
                'notional_value': float(item.get('Max_Notional_Value', 0)),
                'account_equity': float(item.get('Account_Equity', 0))
            })

        # Create strategy document
        strategy_doc = {
            "strategy_id": strategy_id,
            "strategy_name": submission['strategy_name'],
            "name": submission['strategy_name'],
            "asset_class": asset_class,
            "instruments": instruments,
            "accounts": approval_data.get('accounts', []),
            "status": approval_data.get('status', 'ACTIVE'),
            "trading_mode": approval_data.get('trading_mode', 'PAPER'),
            "include_in_optimization": approval_data.get('include_in_optimization', True),
            "developer_contact": approval_data.get('developer_contact', submission['developer_info'].get('email', '')),
            "notes": approval_data.get('notes', ''),
            "risk_limits": approval_data.get('risk_limits', {}),

            # Backtest data - use lowercase format for portfolio construction
            "raw_data_backtest_full": raw_data_lowercase,
            "raw_data_developer_live": [],
            "raw_data_mathematricks_live": [],
            "metrics": submission['metrics'],
            "synthetic_data": submission.get('synthetic_data', {}),

            # Hash tracking
            "backtest_data_hash": backtest_hash,
            "last_backtest_sync": datetime.utcnow(),

            # Link to original submission
            "original_submission_id": submission_id,

            # Timestamps
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Insert strategy
        strategies_collection.insert_one(strategy_doc)

        # Update submission status
        uploaded_strategies_collection.update_one(
            {"submission_id": submission_id},
            {
                "$set": {
                    "status": "APPROVED",
                    "approved_strategy_id": strategy_id,
                    "reviewed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Approved submission {submission_id} → strategy {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy approved and added to portfolio",
            "strategy_id": strategy_id,
            "submission_id": submission_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving submission {submission_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/admin/submissions/{submission_id}/reject")
async def reject_submission(submission_id: str, rejection_data: Dict[str, Any]):
    """
    ADMIN ENDPOINT: Reject a strategy submission

    Request body:
    {
        "rejection_reason": "Insufficient backtest history (need at least 2 years)"
    }
    """
    try:
        # Fetch submission
        submission = uploaded_strategies_collection.find_one({"submission_id": submission_id})

        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

        if submission['status'] != 'PENDING_APPROVAL':
            raise HTTPException(
                status_code=400,
                detail=f"Submission is already {submission['status']}"
            )

        rejection_reason = rejection_data.get('rejection_reason', 'No reason provided')

        # Update submission status
        uploaded_strategies_collection.update_one(
            {"submission_id": submission_id},
            {
                "$set": {
                    "status": "REJECTED",
                    "rejection_reason": rejection_reason,
                    "reviewed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Rejected submission {submission_id}: {rejection_reason}")

        return {
            "status": "success",
            "message": f"Submission rejected",
            "submission_id": submission_id,
            "rejection_reason": rejection_reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting submission {submission_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/admin/submissions/{submission_id}")
async def delete_submission(submission_id: str):
    """
    ADMIN ENDPOINT: Delete a strategy submission

    This permanently removes a submission from the database.
    Use with caution.
    """
    try:
        # Fetch submission
        submission = uploaded_strategies_collection.find_one({"submission_id": submission_id})

        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

        # Delete the submission
        result = uploaded_strategies_collection.delete_one({"submission_id": submission_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete submission")

        logger.info(f"🗑️  Deleted submission {submission_id} (strategy: {submission.get('strategy_name')})")

        return {
            "status": "success",
            "message": "Submission deleted successfully",
            "submission_id": submission_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting submission {submission_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies/{strategy_id}/upload-backtest")
async def upload_backtest_incremental(
    strategy_id: str,
    file: UploadFile = File(...),
    force_replace: bool = Form(False),
    starting_capital: float = Form(1000000.0)
):
    """
    ADMIN ENDPOINT: Upload incremental backtest data for existing strategy

    Handles:
    - Time incremental: Add new dates to existing backtest
    - Column incremental: Add new columns and backfill old rows
    - Overlap detection: Requires force_replace=true to overwrite existing dates
    - Hash tracking: Calculates new hash and invalidates affected allocations

    Form Data:
    - file: CSV file with backtest data
    - force_replace: Allow overwriting existing dates (default: false)
    - starting_capital: For synthetic data generation (default: 1M)

    Returns:
    - upload_summary: Details about rows added/updated and columns generated
    - old_hash: Previous backtest data hash
    - new_hash: New backtest data hash
    - invalidated_allocations: List of allocations marked OUTDATED
    """
    try:
        logger.info(f"📤 Incremental backtest upload for strategy: {strategy_id}")

        # Check if strategy exists
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Get old hash
        old_hash = strategy.get('backtest_data_hash', 'NONE')

        # Read and parse new CSV
        file_content = await file.read()
        new_df = parse_csv(file_content)
        new_df = normalize_returns(new_df)

        # Get existing backtest data
        existing_data = strategy.get('raw_data_backtest_full', [])

        # Merge with existing data
        merged_data, merge_info = merge_backtest_data(
            existing_data,
            new_df,
            force_replace=force_replace,
            starting_capital=starting_capital
        )

        # Calculate new hash
        new_hash = calculate_backtest_hash(merged_data)

        # Recalculate metrics with new data
        new_metrics = calculate_all_metrics(merged_data)

        # Update strategy document
        strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "raw_data_backtest_full": merged_data,
                    "metrics": new_metrics,
                    "backtest_data_hash": new_hash,
                    "last_backtest_sync": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Invalidate allocations if hash changed
        invalidated_allocations = {"count": 0, "allocation_ids": []}
        if new_hash != old_hash:
            invalidated_allocations = invalidate_allocations_for_strategy(
                db,
                strategy_id,
                new_hash,
                reason=f"Strategy {strategy_id} backtest data updated (hash: {old_hash[:12]} → {new_hash[:12]})"
            )

        logger.info(f"✅ Backtest updated: {merge_info['total_rows']} total rows, {merge_info['new_rows']} new")
        logger.info(f"   Hash changed: {old_hash[:12]} → {new_hash[:12]}")
        logger.info(f"   Invalidated {invalidated_allocations['count']} allocations")

        return {
            "status": "success",
            "upload_summary": merge_info,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "invalidated_allocations": invalidated_allocations
        }

    except BacktestUploadError as e:
        logger.error(f"Backtest upload validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading backtest for {strategy_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/allocations/outdated")
async def get_outdated_allocations():
    """
    ADMIN ENDPOINT: Get all OUTDATED allocations

    Returns list of allocations that have been marked OUTDATED due to strategy data changes
    """
    try:
        outdated = list(
            portfolio_allocations_collection.find(
                {"status": "OUTDATED"},
                {'_id': 0}
            ).sort('outdated_at', -1)
        )

        return {
            "status": "success",
            "count": len(outdated),
            "allocations": outdated
        }

    except Exception as e:
        logger.error(f"Error fetching outdated allocations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Portfolio Allocation APIs
# ============================================================================

@app.get("/api/v1/allocations/current")
async def get_current_allocation():
    """
    Get all current active allocations (one per fund)
    Reads from funds.approved_allocation (v5.2 - allocation snapshot)
    """
    try:
        # Get all active funds with approved allocations
        active_funds = list(funds_collection.find({
            "approved_allocation.allocations": {"$exists": True},
            "status": "ACTIVE"
        }))

        allocations_by_fund = {}

        for fund in active_funds:
            fund_id = fund['fund_id']
            approved_allocation = fund.get('approved_allocation', {})

            allocations_dict = approved_allocation.get('allocations', {})
            portfolio_test_id = approved_allocation.get('portfolio_test_id', 'unknown')
            approved_at = approved_allocation.get('approved_at')
            approved_by = approved_allocation.get('approved_by', 'unknown')
            notes = approved_allocation.get('notes', '')

            # Build allocation response in expected format
            allocations_by_fund[fund_id] = {
                "fund_id": fund_id,
                "allocations": allocations_dict,
                "portfolio_test_id": portfolio_test_id,
                "allocation_name": f"Test {portfolio_test_id}",
                "approved_at": approved_at,
                "approved_by": approved_by,
                "notes": notes,
                "updated_at": fund.get('updated_at'),  # For frontend compatibility
                "total_allocation_pct": sum(allocations_dict.values())
            }

        # For backward compatibility, return first allocation if exists
        first_allocation = list(allocations_by_fund.values())[0] if allocations_by_fund else None

        return {
            "status": "success",
            "allocations": allocations_by_fund,
            "allocation": first_allocation
        }
    except Exception as e:
        logger.error(f"Error fetching current allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/v1/allocations/approve")
async def approve_allocation(request: Dict[str, Any]):
    """
    Approve allocation by creating snapshot in fund.approved_allocation (v5.2).
    Captures full allocation dictionary + metadata at approval time.
    Supports manual edits made in Allocation Editor.
    """
    try:
        portfolio_test_id = request.get('portfolio_test_id')
        fund_id = request.get('fund_id')
        allocations = request.get('allocations')  # NEW: Optional - if provided, use this (manual edits)
        approved_by = request.get('approved_by', 'system')  # NEW: Who approved
        notes = request.get('notes', '')  # NEW: Optional approval notes

        if not portfolio_test_id:
            raise HTTPException(status_code=400, detail="portfolio_test_id is required")
        if not fund_id:
            raise HTTPException(status_code=400, detail="fund_id is required")

        # Verify fund exists
        fund = funds_collection.find_one({"fund_id": fund_id})
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund {fund_id} not found")

        # If allocations not provided, fetch from portfolio_test (original allocation)
        if not allocations:
            test = portfolio_tests_collection.find_one({"test_id": portfolio_test_id})
            if not test:
                raise HTTPException(status_code=404, detail=f"Portfolio test {portfolio_test_id} not found")
            allocations = test.get('allocations', {})

        # Create allocation snapshot
        approved_allocation = {
            "portfolio_test_id": portfolio_test_id,
            "allocations": allocations,  # Full allocation dictionary snapshot
            "approved_at": datetime.utcnow(),
            "approved_by": approved_by,
            "notes": notes
        }

        # Update fund with allocation snapshot
        funds_collection.update_one(
            {"fund_id": fund_id},
            {
                "$set": {
                    "approved_allocation": approved_allocation,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "portfolio_test_id": "",  # Remove old field if exists
                    "allocation_approved_at": ""  # Remove old field if exists
                }
            }
        )

        logger.info(f"✅ Approved allocation: Fund {fund_id} → Test {portfolio_test_id}")
        logger.info(f"   Allocations snapshot: {allocations}")
        logger.info(f"   Approved by: {approved_by}")
        if notes:
            logger.info(f"   Notes: {notes}")

        return {
            "success": True,
            "fund_id": fund_id,
            "portfolio_test_id": portfolio_test_id,
            "approved_allocation": approved_allocation,
            "message": f"Allocation approved for fund {fund_id}"
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
# Fund Management API (v5)
# ============================================================================

# Initialize funds collection
funds_collection = db['funds']
trading_accounts_collection = db['trading_accounts']


@app.post("/api/v1/funds")
async def create_fund(fund_data: dict):
    """
    Create a new fund
    
    Request body:
    {
        "name": "Mathematricks Capital Fund 1",
        "description": "Main production fund",
        "currency": "USD",
        "accounts": []  # optional
    }
    """
    try:
        # Generate fund_id from name (slugify)
        fund_id = fund_data.get('name', '').lower().replace(' ', '-').replace('_', '-')
        fund_id = re.sub(r'[^a-z0-9-]', '', fund_id)  # Remove special chars
        
        if not fund_id:
            raise HTTPException(status_code=400, detail="Fund name cannot be empty")
        
        # Check if fund_id already exists
        if funds_collection.find_one({"fund_id": fund_id}):
            raise HTTPException(status_code=400, detail=f"Fund with ID '{fund_id}' already exists")
        
        # Create fund document
        fund_doc = {
            "fund_id": fund_id,
            "name": fund_data.get('name'),
            "description": fund_data.get('description', ''),
            "total_equity": 0.0,  # Will be calculated from accounts
            "currency": fund_data.get('currency', 'USD'),
            "accounts": fund_data.get('accounts', []),
            "status": "ACTIVE",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = funds_collection.insert_one(fund_doc)
        fund_doc['_id'] = str(result.inserted_id)
        
        logger.info(f"Created fund: {fund_id}")
        return {"status": "success", "fund": fund_doc}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating fund: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/funds")
async def get_funds(status: Optional[str] = None):
    """
    Get all funds
    
    Query params:
    - status: Filter by status (ACTIVE, PAUSED, CLOSED)
    """
    try:
        query = {}
        if status:
            query['status'] = status.upper()
        
        funds = list(funds_collection.find(query))
        
        # Convert ObjectId to string
        for fund in funds:
            fund['_id'] = str(fund['_id'])
        
        return {"status": "success", "count": len(funds), "funds": funds}
    
    except Exception as e:
        logger.error(f"Error fetching funds: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/funds/{fund_id}")
async def get_fund(fund_id: str):
    """Get fund details by ID"""
    try:
        fund = funds_collection.find_one({"fund_id": fund_id})
        
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund '{fund_id}' not found")
        
        fund['_id'] = str(fund['_id'])
        
        # Get accounts for this fund
        accounts = list(trading_accounts_collection.find({"fund_id": fund_id}))
        for acc in accounts:
            acc['_id'] = str(acc['_id'])
        
        fund['account_details'] = accounts
        
        return {"status": "success", "fund": fund}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching fund {fund_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/funds/{fund_id}")
async def update_fund(fund_id: str, update_data: dict):
    """
    Update fund
    
    Allowed updates: name, description, accounts, status
    Cannot update: fund_id, total_equity (auto-calculated)
    """
    try:
        fund = funds_collection.find_one({"fund_id": fund_id})
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund '{fund_id}' not found")
        
        # Allowed fields to update
        allowed_fields = ['name', 'description', 'accounts', 'status']
        update_doc = {}
        
        for field in allowed_fields:
            if field in update_data:
                update_doc[field] = update_data[field]
        
        if not update_doc:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        update_doc['updated_at'] = datetime.utcnow()
        
        funds_collection.update_one(
            {"fund_id": fund_id},
            {"$set": update_doc}
        )
        
        logger.info(f"Updated fund {fund_id}: {update_doc}")
        
        # Return updated fund
        updated_fund = funds_collection.find_one({"fund_id": fund_id})
        updated_fund['_id'] = str(updated_fund['_id'])
        
        return {"status": "success", "fund": updated_fund}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating fund {fund_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/funds/{fund_id}")
async def delete_fund(fund_id: str):
    """
    Delete fund
    
    Validation: Cannot delete if has ACTIVE allocations
    """
    try:
        fund = funds_collection.find_one({"fund_id": fund_id})
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund '{fund_id}' not found")
        
        # Check for active allocations
        active_alloc = current_allocation_collection.find_one({
            "fund_id": fund_id,
            "status": "ACTIVE"
        })
        
        if active_alloc:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete fund with ACTIVE allocations. Archive allocations first."
            )
        
        # Set fund_id=null on accounts
        trading_accounts_collection.update_many(
            {"fund_id": fund_id},
            {"$set": {"fund_id": None, "updated_at": datetime.utcnow()}}
        )
        
        # Delete fund
        funds_collection.delete_one({"fund_id": fund_id})
        
        logger.info(f"Deleted fund: {fund_id}")
        return {"status": "success", "message": f"Fund '{fund_id}' deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting fund {fund_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _recalculate_fund_equity(fund_id: str):
    """
    Recalculate and update fund's total_equity from all its accounts.
    Called after account creation/update/deletion to keep fund.total_equity in sync.
    """
    try:
        # Get all active accounts for this fund
        accounts = list(trading_accounts_collection.find({
            "fund_id": fund_id,
            "status": "ACTIVE"
        }))
        
        # Sum up equity from all accounts (using balances.equity)
        total_equity = sum(acc.get('balances', {}).get('equity', 0.0) for acc in accounts)
        
        # Update fund
        funds_collection.update_one(
            {"fund_id": fund_id},
            {
                "$set": {
                    "total_equity": total_equity,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Recalculated fund {fund_id} total_equity: ${total_equity:,.2f} from {len(accounts)} accounts")
        return total_equity
    except Exception as e:
        logger.error(f"Error recalculating fund equity for {fund_id}: {e}")
        return 0.0


# ============================================================================
# Account Management API (v5)
# ============================================================================

@app.post("/api/v1/accounts")
async def create_account(account_data: dict):
    """
    Create a new trading account
    
    Request body:
    {
        "account_id": "IBKR_Main",
        "broker": "IBKR",
        "broker_account_number": "DU123456",
        "fund_id": "mathematricks-1",
        "asset_classes": {
            "equity": ["all"],
            "futures": ["all"],
            "crypto": [],
            "forex": ["all"]
        }
    }
    """
    try:
        account_id = account_data.get('account_id')
        if not account_id:
            raise HTTPException(status_code=400, detail="account_id is required")
        
        # Check if account_id already exists
        if trading_accounts_collection.find_one({"account_id": account_id}):
            raise HTTPException(status_code=400, detail=f"Account '{account_id}' already exists")
        
        # Verify fund exists
        fund_id = account_data.get('fund_id')
        if fund_id:
            fund = funds_collection.find_one({"fund_id": fund_id})
            if not fund:
                raise HTTPException(status_code=400, detail=f"Fund '{fund_id}' not found")
        
        # Get authentication details and calculate initial equity
        auth_details = account_data.get('authentication_details', {})
        broker = account_data.get('broker')
        
        # For Mock brokers, use initial_equity from auth_details
        initial_equity = 0.0
        if auth_details.get('auth_type') == 'MOCK':
            initial_equity = auth_details.get('initial_equity', 1000000)
        
        # Generate account metadata (matches OANDA_MOCK structure)
        account_type = "Paper" if auth_details.get('auth_type') == 'MOCK' or 'paper' in account_id.lower() else "Live"
        account_number = f"MOCK_{account_id}" if broker == "Mock" else account_data.get('broker_account_number', '')
        account_name = f"{account_id} {broker} {account_type} Trading"
        
        # Create account document - matches OANDA_MOCK structure exactly
        # NOTE: NO top-level balance fields (equity, cash_balance, etc) - only balances object
        account_doc = {
            "account_id": account_id,
            "broker": broker,
            "broker_account_number": account_data.get('broker_account_number', ''),
            "fund_id": fund_id,
            "asset_classes": account_data.get('asset_classes', {
                "equity": [],
                "futures": [],
                "options": [],
                "crypto": [],
                "forex": [],
                "commodities": []
            }),
            "authentication_details": auth_details,
            "balances": {
                "equity": initial_equity,
                "cash": initial_equity / 2,
                "cash_balance": initial_equity / 2,
                "margin_used": 0.0,
                "margin_available": initial_equity / 2,
                "buying_power": initial_equity * 2,  # 2x leverage for margin accounts
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "last_updated": datetime.utcnow()
            },
            "account_name": account_name,
            "account_number": account_number,
            "account_type": account_type,
            "open_positions": [],
            "status": "ACTIVE",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = trading_accounts_collection.insert_one(account_doc)
        account_doc['_id'] = str(result.inserted_id)
        
        # Add account to fund's accounts array and recalculate total_equity
        if fund_id:
            funds_collection.update_one(
                {"fund_id": fund_id},
                {
                    "$addToSet": {"accounts": account_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            # Recalculate fund's total_equity from all accounts
            _recalculate_fund_equity(fund_id)
        
        logger.info(f"Created account: {account_id} for fund: {fund_id}")
        return {"status": "success", "account": account_doc}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/accounts")
async def get_accounts(fund_id: Optional[str] = None):
    """
    Get all accounts
    
    Query params:
    - fund_id: Filter by fund
    """
    try:
        query = {}
        if fund_id:
            query['fund_id'] = fund_id
        
        accounts = list(trading_accounts_collection.find(query))
        
        # Convert ObjectId to string
        for acc in accounts:
            acc['_id'] = str(acc['_id'])
        
        return {"status": "success", "count": len(accounts), "accounts": accounts}
    
    except Exception as e:
        logger.error(f"Error fetching accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/accounts/{account_id}")
async def update_account(account_id: str, update_data: dict):
    """
    Update account
    
    Allowed updates: fund_id, asset_classes, status
    Cannot update: account_id, broker (immutable)
    """
    try:
        account = trading_accounts_collection.find_one({"account_id": account_id})
        if not account:
            raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")
        
        # Allowed fields to update
        allowed_fields = ['fund_id', 'asset_classes', 'status', 'broker_account_number']
        update_doc = {}
        
        for field in allowed_fields:
            if field in update_data:
                # If changing fund_id, verify new fund exists
                if field == 'fund_id' and update_data[field]:
                    fund = funds_collection.find_one({"fund_id": update_data[field]})
                    if not fund:
                        raise HTTPException(status_code=400, detail=f"Fund '{update_data[field]}' not found")
                
                update_doc[field] = update_data[field]
        
        if not update_doc:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        update_doc['updated_at'] = datetime.utcnow()
        
        # Remove from old fund's accounts array
        old_fund_id = account.get('fund_id')
        if old_fund_id and 'fund_id' in update_doc and update_doc['fund_id'] != old_fund_id:
            funds_collection.update_one(
                {"fund_id": old_fund_id},
                {
                    "$pull": {"accounts": account_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        
        # Add to new fund's accounts array
        new_fund_id = update_doc.get('fund_id')
        if new_fund_id and new_fund_id != old_fund_id:
            funds_collection.update_one(
                {"fund_id": new_fund_id},
                {
                    "$addToSet": {"accounts": account_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        
        trading_accounts_collection.update_one(
            {"account_id": account_id},
            {"$set": update_doc}
        )
        
        logger.info(f"Updated account {account_id}: {update_doc}")
        
        # Return updated account
        updated_account = trading_accounts_collection.find_one({"account_id": account_id})
        updated_account['_id'] = str(updated_account['_id'])
        
        return {"status": "success", "account": updated_account}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating account {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/accounts/{account_id}")
async def delete_account(account_id: str):
    """
    Delete account
    
    Validation: No open positions
    """
    try:
        account = trading_accounts_collection.find_one({"account_id": account_id})
        if not account:
            raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")
        
        # Check for open positions
        if account.get('open_positions') and len(account['open_positions']) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete account with open positions"
            )
        
        fund_id = account.get('fund_id')
        
        # Remove from fund's accounts array
        if fund_id:
            funds_collection.update_one(
                {"fund_id": fund_id},
                {
                    "$pull": {"accounts": account_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        
        # Delete account
        trading_accounts_collection.delete_one({"account_id": account_id})
        
        logger.info(f"Deleted account: {account_id}")
        return {"status": "success", "message": f"Account '{account_id}' deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Strategy-Account Mapping API (v5)
# ============================================================================

@app.put("/api/v1/strategies/{strategy_id}/accounts")
async def update_strategy_accounts(strategy_id: str, data: dict):
    """
    Update allowed accounts for a strategy
    
    Request body:
    {
        "accounts": ["IBKR_Main", "IBKR_Futures"]
    }
    """
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
        
        accounts = data.get('accounts', [])
        
        # Validate all accounts exist
        for acc_id in accounts:
            acc = trading_accounts_collection.find_one({"account_id": acc_id})
            if not acc:
                raise HTTPException(status_code=400, detail=f"Account '{acc_id}' not found")
            
            # Validate asset class compatibility
            strategy_asset_class = strategy.get('asset_class', '').lower()
            acc_asset_classes = acc.get('asset_classes', {})
            
            if strategy_asset_class == 'equity' and not acc_asset_classes.get('equity'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Account '{acc_id}' does not support equity trading (required by strategy)"
                )
            elif strategy_asset_class == 'futures' and not acc_asset_classes.get('futures'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Account '{acc_id}' does not support futures trading (required by strategy)"
                )
            elif strategy_asset_class == 'crypto' and not acc_asset_classes.get('crypto'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Account '{acc_id}' does not support crypto trading (required by strategy)"
                )
            elif strategy_asset_class == 'forex' and not acc_asset_classes.get('forex'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Account '{acc_id}' does not support forex trading (required by strategy)"
                )
        
        # Update strategy
        strategies_collection.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "accounts": accounts,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Updated strategy {strategy_id} accounts: {accounts}")
        
        # Return updated strategy
        updated_strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        updated_strategy['_id'] = str(updated_strategy['_id'])
        
        return {"status": "success", "strategy": updated_strategy}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/strategies/{strategy_id}/accounts")
async def get_strategy_accounts(strategy_id: str):
    """Get account mapping for a strategy"""
    try:
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
        
        return {
            "status": "success",
            "strategy_id": strategy_id,
            "accounts": strategy.get('accounts', []),
            "asset_class": strategy.get('asset_class', '')
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching strategy accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting PortfolioBuilder Service on port 8003")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")

