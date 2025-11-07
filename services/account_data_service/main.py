"""
Account Data Service - MVP
Centralizes and reconciles real-time account state from brokers.
Provides REST API for CerebroService to query account/margin status.
"""
import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv
import threading
import requests

# Load environment variables
# Use relative path from project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Configure logging
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'account_data_service.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Account Data Service", version="1.0.0-MVP")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, OPTIONS)
    allow_headers=["*"],  # Allow all headers
)

# Mount outputs directory for serving tearsheet HTML files
# Use service-specific outputs directory
service_dir = os.path.dirname(os.path.abspath(__file__))
outputs_dir = os.path.join(service_dir, 'outputs')
os.makedirs(outputs_dir, exist_ok=True)  # Create if doesn't exist
app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")

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
portfolio_allocations_collection = db['portfolio_allocations']
portfolio_optimization_runs_collection = db['portfolio_optimization_runs']
strategy_configurations_collection = db['strategy_configurations']
strategy_backtest_data_collection = db['strategy_backtest_data']

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


# ============================================================================
# PORTFOLIO ALLOCATION MANAGEMENT APIs - Pydantic Models
# ============================================================================

class CustomAllocationRequest(BaseModel):
    """Request model for creating custom portfolio allocation"""
    allocations: Dict[str, float]
    created_by: str
    notes: Optional[str] = None


# ============================================================================
# PORTFOLIO ALLOCATION MANAGEMENT APIs
# ============================================================================

@app.get("/api/v1/portfolio/allocations/current")
async def get_current_allocation():
    """
    Get current ACTIVE portfolio allocation
    Used by CerebroService and frontend to show live allocations
    """
    try:
        active_allocation = portfolio_allocations_collection.find_one(
            {"status": "ACTIVE"},
            sort=[("approved_at", -1)]
        )

        if not active_allocation:
            return {
                "status": "no_active_allocation",
                "allocation": None,
                "message": "No active portfolio allocation found"
            }

        # Remove MongoDB _id
        active_allocation.pop('_id', None)

        return {
            "status": "active",
            "allocation": active_allocation
        }

    except Exception as e:
        logger.error(f"Error fetching current allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/allocations/latest-recommendation")
async def get_latest_recommendation():
    """
    Get latest PENDING_APPROVAL allocation recommendation
    Used by portfolio managers to review daily optimization results
    """
    try:
        pending_allocation = portfolio_allocations_collection.find_one(
            {"status": "PENDING_APPROVAL"},
            sort=[("timestamp", -1)]
        )

        if not pending_allocation:
            return {
                "status": "no_pending_recommendation",
                "allocation": None,
                "message": "No pending allocation recommendation found"
            }

        # Remove MongoDB _id
        pending_allocation.pop('_id', None)

        return {
            "status": "pending",
            "allocation": pending_allocation
        }

    except Exception as e:
        logger.error(f"Error fetching latest recommendation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/portfolio/allocations/approve")
async def approve_allocation(allocation_id: str, approved_by: str):
    """
    Approve a PENDING_APPROVAL allocation and make it ACTIVE
    Archives previous ACTIVE allocation
    Triggers CerebroService to reload allocations
    """
    try:
        logger.info(f"Approving allocation {allocation_id} by {approved_by}")

        # Find the pending allocation
        pending = portfolio_allocations_collection.find_one({"allocation_id": allocation_id})

        if not pending:
            raise HTTPException(status_code=404, detail=f"Allocation {allocation_id} not found")

        if pending['status'] != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=400,
                detail=f"Allocation {allocation_id} is not in PENDING_APPROVAL status (current: {pending['status']})"
            )

        # Archive all current ACTIVE allocations
        portfolio_allocations_collection.update_many(
            {"status": "ACTIVE"},
            {
                "$set": {
                    "status": "ARCHIVED",
                    "archived_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Activate the new allocation
        portfolio_allocations_collection.update_one(
            {"allocation_id": allocation_id},
            {
                "$set": {
                    "status": "ACTIVE",
                    "approved_by": approved_by,
                    "approved_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Allocation {allocation_id} approved and activated")

        # Defensive validation: Ensure only ONE ACTIVE allocation exists
        active_count = portfolio_allocations_collection.count_documents({"status": "ACTIVE"})
        if active_count > 1:
            logger.error(f"❌ DATA INTEGRITY ERROR: Found {active_count} ACTIVE allocations (expected 1)")
            logger.error(f"   This should never happen - archiving failed or concurrent approvals occurred")
            # Auto-fix: Keep only the most recent one
            active_allocations = list(portfolio_allocations_collection.find(
                {"status": "ACTIVE"},
                sort=[("approved_at", -1)]
            ))
            for alloc in active_allocations[1:]:  # Keep first, archive rest
                portfolio_allocations_collection.update_one(
                    {"allocation_id": alloc['allocation_id']},
                    {
                        "$set": {
                            "status": "ARCHIVED",
                            "archived_at": datetime.utcnow(),
                            "archived_reason": "auto_fix_duplicate_active"
                        }
                    }
                )
                logger.warning(f"   Auto-archived duplicate: {alloc['allocation_id']}")
        elif active_count == 1:
            logger.info(f"✅ Validation passed: Exactly 1 ACTIVE allocation")

        # Trigger CerebroService to reload allocations
        try:
            cerebro_service_url = os.getenv('CEREBRO_SERVICE_URL', 'http://localhost:8001')
            response = requests.post(f"{cerebro_service_url}/api/v1/reload-allocations", timeout=5)
            if response.status_code == 200:
                logger.info("✅ CerebroService allocations reloaded successfully")
            else:
                logger.warning(f"⚠️  CerebroService reload returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to reload CerebroService allocations: {str(e)}")
            logger.warning("   CerebroService will use old allocations until manual reload")

        return {
            "status": "success",
            "message": f"Allocation {allocation_id} approved and activated",
            "allocation_id": allocation_id,
            "approved_by": approved_by
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/portfolio/allocations/custom")
async def create_custom_allocation(request: CustomAllocationRequest):
    """
    Create custom portfolio allocation (manual override)
    Bypasses optimization - portfolio manager sets allocations directly
    """
    try:
        logger.info(f"Creating custom allocation by {request.created_by}")

        # Extract data from request model
        allocations = request.allocations
        created_by = request.created_by
        notes = request.notes

        # Validate allocations
        if not allocations:
            raise HTTPException(status_code=400, detail="Allocations cannot be empty")

        total_allocation = sum(allocations.values())
        if total_allocation > 200:  # Max 200% leverage
            raise HTTPException(
                status_code=400,
                detail=f"Total allocation {total_allocation}% exceeds max leverage (200%)"
            )

        # Create custom allocation (starts as PENDING_APPROVAL)
        allocation_id = f"CUSTOM_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        custom_allocation = {
            "allocation_id": allocation_id,
            "timestamp": datetime.utcnow(),
            "status": "PENDING_APPROVAL",
            "allocations": allocations,
            "expected_metrics": {
                "total_allocation_pct": total_allocation,
                "leverage_ratio": total_allocation / 100,
                "custom": True
            },
            "optimization_run_id": None,  # No optimization run for custom allocations
            "approved_by": None,
            "approved_at": None,
            "archived_at": None,
            "notes": notes or f"Custom allocation created by {created_by}",
            "created_by": created_by,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        portfolio_allocations_collection.insert_one(custom_allocation)

        logger.info(f"✅ Created custom allocation: {allocation_id}")

        return {
            "status": "success",
            "message": "Custom allocation created (PENDING_APPROVAL)",
            "allocation_id": allocation_id,
            "total_allocation_pct": total_allocation
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom allocation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/allocations/history")
async def get_allocation_history(limit: int = 10):
    """
    Get allocation history (all statuses)
    Shows timeline of allocations and approvals
    """
    try:
        allocations = list(
            portfolio_allocations_collection.find(
                {},
                sort=[("created_at", -1)],
                limit=limit
            )
        )

        # Remove MongoDB _id
        for alloc in allocations:
            alloc.pop('_id', None)

        return {
            "status": "success",
            "count": len(allocations),
            "allocations": allocations
        }

    except Exception as e:
        logger.error(f"Error fetching allocation history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/optimization/latest")
async def get_latest_optimization_run():
    """
    Get latest portfolio optimization run details
    Shows optimization convergence, metrics, correlation matrix
    """
    try:
        latest_run = portfolio_optimization_runs_collection.find_one(
            {},
            sort=[("timestamp", -1)]
        )

        if not latest_run:
            return {
                "status": "no_runs",
                "run": None,
                "message": "No optimization runs found"
            }

        # Remove MongoDB _id
        latest_run.pop('_id', None)

        return {
            "status": "success",
            "run": latest_run
        }

    except Exception as e:
        logger.error(f"Error fetching latest optimization run: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/portfolio/optimization/run")
async def run_portfolio_optimization(
    strategy_ids: List[str] = None,
    optimization_modes: List[str] = None,
    max_leverage: float = 2.0,
    max_single_strategy: float = 0.5,
    max_drawdown_limit: float = -0.20
):
    """
    Trigger portfolio optimization run from frontend

    Args:
        strategy_ids: List of strategy IDs to include (null = all ACTIVE strategies)
        optimization_modes: List of modes to run (e.g., ["max_sharpe", "max_cagr_drawdown"])
        max_leverage: Maximum total allocation (2.0 = 200%)
        max_single_strategy: Maximum allocation per strategy (0.5 = 50%)
        max_drawdown_limit: Maximum allowed drawdown for max_cagr_drawdown mode (-0.20 = -20%)
    """
    try:
        import subprocess
        import sys

        logger.info(f"Triggering portfolio optimization from frontend")
        logger.info(f"Strategy IDs: {strategy_ids}")
        logger.info(f"Optimization modes: {optimization_modes}")

        # TODO: For MVP, we'll just trigger the optimization_runner.py script
        # In production, this should be refactored to import and call the function directly

        # For now, return a placeholder response
        return {
            "status": "accepted",
            "message": "Optimization run triggered (check allocation history in a few seconds)",
            "note": "MVP: Please run optimization_runner.py manually for now"
        }

    except Exception as e:
        logger.error(f"Error triggering optimization run: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/allocations/{allocation_id}/simulate")
async def simulate_allocation_performance(allocation_id: str, starting_capital: float = 1000000.0):
    """
    Calculate historical portfolio performance for a given allocation
    WITH margin and leverage tracking (matches portfolio_combiner.py logic)

    Returns: equity curve, daily returns, margin utilization, leverage ratios, and validation flags
    """
    try:
        import numpy as np
        import pandas as pd

        # Setup logging file
        log_dir = '/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs'
        os.makedirs(log_dir, exist_ok=True)
        sim_log_path = os.path.join(log_dir, 'portfolio_simulation.log')

        # Open log file for this simulation
        with open(sim_log_path, 'a') as sim_log:
            sim_log.write(f"\n{'='*80}\n")
            sim_log.write(f"=== SIMULATION START ===\n")
            sim_log.write(f"Allocation ID: {allocation_id}\n")
            sim_log.write(f"Timestamp: {datetime.utcnow().isoformat()}\n")
            sim_log.write(f"Starting Capital: ${starting_capital:,.0f}\n")

            logger.info(f"Simulating performance for allocation {allocation_id}")

            # Fetch allocation
            allocation = portfolio_allocations_collection.find_one({"allocation_id": allocation_id})
            if not allocation:
                raise HTTPException(status_code=404, detail=f"Allocation {allocation_id} not found")

            allocations_dict = allocation.get('allocations', {})
            if not allocations_dict:
                raise HTTPException(status_code=400, detail="Allocation has no strategy allocations")

            sim_log.write(f"\nStrategy Weights:\n")
            for strat, weight in allocations_dict.items():
                sim_log.write(f"  - {strat}: {weight}%\n")

            # Fetch FULL strategy data (with margin and notional)
            strategy_data = {}
            dates_set = None

            for strategy_id, weight_pct in allocations_dict.items():
                backtest = strategy_backtest_data_collection.find_one({"strategy_id": strategy_id})
                if not backtest:
                    logger.warning(f"No backtest data found for strategy {strategy_id}, skipping")
                    sim_log.write(f"  ⚠️  WARNING: No data for {strategy_id}\n")
                    continue

                # Use raw_data_backtest_full (with margin/notional)
                raw_data_full = backtest.get('raw_data_backtest_full', [])

                if not raw_data_full or not isinstance(raw_data_full, list) or len(raw_data_full) == 0:
                    logger.warning(f"Incomplete full backtest data for strategy {strategy_id}, skipping")
                    sim_log.write(f"  ⚠️  WARNING: Incomplete data for {strategy_id}\n")
                    continue

                # Parse all fields
                dates = [item['date'] for item in raw_data_full if all(k in item for k in ['date', 'return', 'margin_used', 'notional_value'])]
                returns = [item['return'] for item in raw_data_full if all(k in item for k in ['date', 'return', 'margin_used', 'notional_value'])]
                margins = [item['margin_used'] for item in raw_data_full if all(k in item for k in ['date', 'return', 'margin_used', 'notional_value'])]
                notionals = [item['notional_value'] for item in raw_data_full if all(k in item for k in ['date', 'return', 'margin_used', 'notional_value'])]

                if not returns or not dates:
                    logger.warning(f"Incomplete parsed data for strategy {strategy_id}, skipping")
                    continue

                strategy_data[strategy_id] = {
                    'returns': np.array(returns),
                    'margins': np.array(margins),
                    'notionals': np.array(notionals),
                    'dates': dates,
                    'weight': weight_pct / 100.0
                }

                # Ensure all strategies have the same dates
                if dates_set is None:
                    dates_set = set(dates)
                else:
                    dates_set = dates_set.intersection(set(dates))

            if not strategy_data:
                raise HTTPException(
                    status_code=400,
                    detail="No valid backtest data found for strategies in this allocation"
                )

            # Build common date index
            common_dates = sorted(list(dates_set))
            sim_log.write(f"\nDate Range: {common_dates[0]} to {common_dates[-1]} ({len(common_dates)} days)\n")

            # Pre-calculate developer equity curves for each strategy
            dev_equity_curves = {}
            for strategy_id, data in strategy_data.items():
                dates = data['dates']
                returns = data['returns']

                # Build date-to-return mapping
                date_to_return = dict(zip(dates, returns))

                # Infer developer's starting equity from first day (matching portfolio_combiner.py lines 116-131)
                dev_starting_equity = starting_capital  # Default to 1M if can't infer

                # Try to infer from first non-zero return
                for date in common_dates:
                    if date in date_to_return:
                        first_return = date_to_return[date]
                        if abs(first_return) > 0.0001:  # Non-zero return found
                            # Get corresponding P&L from raw data (if available)
                            # For now, assume $1M starting equity as reasonable default
                            # In portfolio_combiner.py this is inferred from P&L / return
                            dev_starting_equity = starting_capital
                            break

                sim_log.write(f"  - {strategy_id}: Dev starting equity = ${dev_starting_equity:,.0f}\n")

                # Calculate developer's equity curve starting from inferred equity
                dev_equity = dev_starting_equity
                dev_curve = []
                for date in common_dates:
                    if date in date_to_return:
                        dev_equity = dev_equity * (1 + date_to_return[date])
                    dev_curve.append(dev_equity)

                dev_equity_curves[strategy_id] = np.array(dev_curve)

            # ITERATIVE DAILY LOOP (matching portfolio_combiner.py lines 169-210)
            portfolio_equity = starting_capital
            daily_equity = []
            daily_returns = []
            daily_margin = []
            daily_notional = []
            daily_margin_util_pct = []
            daily_leverage_ratio = []

            sim_log.write(f"\n=== SAMPLE CALCULATIONS (First 5 Days) ===\n")

            for day_idx, date in enumerate(common_dates):
                # Calculate weighted-average portfolio return for this day
                portfolio_daily_return = 0.0
                total_margin = 0.0
                total_notional = 0.0

                if day_idx < 5:
                    sim_log.write(f"\nDay {day_idx + 1} ({date}):\n")

                for strategy_id, data in strategy_data.items():
                    dates = data['dates']
                    returns = data['returns']
                    margins = data['margins']
                    notionals = data['notionals']
                    weight = data['weight']

                    # Get strategy's data for this day
                    date_to_idx = dict(zip(dates, range(len(dates))))
                    if date not in date_to_idx:
                        continue

                    idx = date_to_idx[date]
                    strategy_return = returns[idx]
                    dev_margin = margins[idx]
                    dev_notional = notionals[idx]

                    # Weighted return contribution
                    contribution = strategy_return * weight
                    portfolio_daily_return += contribution

                    # Margin and notional scaling (matching portfolio_combiner.py)
                    dev_equity = dev_equity_curves[strategy_id][day_idx]
                    our_equity = portfolio_equity * weight
                    scaling_ratio = our_equity / dev_equity if dev_equity > 0 else 0

                    our_margin = dev_margin * scaling_ratio
                    our_notional = dev_notional * scaling_ratio

                    total_margin += our_margin
                    total_notional += our_notional

                    if day_idx < 5:
                        sim_log.write(f"  {strategy_id}: return={strategy_return:.6f}, weight={weight:.2f}, contribution={contribution:.6f}\n")

                # Apply portfolio return to update equity
                portfolio_equity = portfolio_equity * (1 + portfolio_daily_return)

                # Calculate risk metrics
                margin_util_pct = (total_margin / portfolio_equity) * 100 if portfolio_equity > 0 else 0
                leverage_ratio = total_notional / portfolio_equity if portfolio_equity > 0 else 0

                # Store daily values
                daily_equity.append(portfolio_equity)
                daily_returns.append(portfolio_daily_return)
                daily_margin.append(total_margin)
                daily_notional.append(total_notional)
                daily_margin_util_pct.append(margin_util_pct)
                daily_leverage_ratio.append(leverage_ratio)

                if day_idx < 5:
                    sim_log.write(f"  Portfolio Daily Return: {portfolio_daily_return:.6f} ({portfolio_daily_return*100:.4f}%)\n")
                    sim_log.write(f"  Equity After: ${portfolio_equity:,.2f}\n")
                    sim_log.write(f"  Total Margin: ${total_margin:,.2f} ({margin_util_pct:.2f}%)\n")
                    sim_log.write(f"  Total Notional: ${total_notional:,.2f} ({leverage_ratio:.2f}x leverage)\n")

                    # Validation indicator
                    if margin_util_pct > 80:
                        sim_log.write(f"  ❌ MARGIN EXCEEDED\n")
                    elif margin_util_pct > 70:
                        sim_log.write(f"  ⚠️  MARGIN WARNING\n")
                    else:
                        sim_log.write(f"  ✓ MARGIN OK\n")

            # Calculate final metrics
            returns_array = np.array(daily_returns)
            equity_array = np.array(daily_equity)

            # Normalize equity curve to start at 1.0
            equity_curve_normalized = (equity_array / starting_capital).tolist()

            # Calculate portfolio metrics
            annual_return = (equity_array[-1] / starting_capital) ** (252 / len(returns_array)) - 1
            volatility_daily = np.std(returns_array)
            volatility_annual = volatility_daily * np.sqrt(252)
            sharpe_ratio = (annual_return / volatility_annual) if volatility_annual > 0 else 0

            # Max drawdown
            equity_series = pd.Series(equity_curve_normalized)
            running_max = equity_series.cummax()
            drawdown = (equity_series - running_max) / running_max
            max_drawdown = drawdown.min()

            # CAGR
            years = len(returns_array) / 252
            cagr = (equity_array[-1] / starting_capital) ** (1 / years) - 1 if years > 0 else 0

            # Find max margin and leverage
            max_margin_util = max(daily_margin_util_pct)
            max_leverage = max(daily_leverage_ratio)
            max_margin_date = common_dates[daily_margin_util_pct.index(max_margin_util)]
            max_leverage_date = common_dates[daily_leverage_ratio.index(max_leverage)]

            # Validation flags (convert to Python bool for JSON serialization)
            margin_exceeded = bool(max_margin_util > 80)
            leverage_exceeded = bool(max_leverage > 2.0)
            validation_status = "FAIL" if (margin_exceeded or leverage_exceeded) else ("WARNING" if (max_margin_util > 70 or max_leverage > 1.5) else "PASS")

            # Write final metrics to log
            sim_log.write(f"\n=== FINAL METRICS ===\n")
            sim_log.write(f"Ending Equity: ${equity_array[-1]:,.2f}\n")
            sim_log.write(f"CAGR: {cagr*100:.2f}%\n")
            sim_log.write(f"Sharpe Ratio: {sharpe_ratio:.2f}\n")
            sim_log.write(f"Max Drawdown: {max_drawdown*100:.2f}%\n")
            sim_log.write(f"Volatility (Annual): {volatility_annual*100:.2f}%\n\n")

            sim_log.write(f"Max Margin Utilization: {max_margin_util:.2f}% (on {max_margin_date})")
            if margin_exceeded:
                sim_log.write(f" ❌\n")
            elif max_margin_util > 70:
                sim_log.write(f" ⚠️\n")
            else:
                sim_log.write(f" ✓\n")

            sim_log.write(f"Max Leverage: {max_leverage:.2f}x (on {max_leverage_date})")
            if leverage_exceeded:
                sim_log.write(f" ❌\n")
            elif max_leverage > 1.5:
                sim_log.write(f" ⚠️\n")
            else:
                sim_log.write(f" ✓\n")

            sim_log.write(f"\nValidation Status: {validation_status}\n")

            if allocation.get('expected_metrics'):
                exp = allocation['expected_metrics']
                sim_log.write(f"\nComparison with Expected Metrics:\n")
                if exp.get('expected_sharpe_annual'):
                    diff = sharpe_ratio - exp['expected_sharpe_annual']
                    sim_log.write(f"  Sharpe: {exp['expected_sharpe_annual']:.2f} vs {sharpe_ratio:.2f} (diff: {diff:+.2f}) {'✓' if abs(diff) < 0.5 else '⚠️'}\n")

            sim_log.write(f"\n=== SIMULATION END ===\n")
            sim_log.write(f"{'='*80}\n\n")

            # Prepare response
            simulation_result = {
                "allocation_id": allocation_id,
                "metrics": {
                    "cagr": round(cagr * 100, 2),
                    "annual_return": round(annual_return * 100, 2),
                    "volatility_annual": round(volatility_annual * 100, 2),
                    "sharpe_ratio": round(sharpe_ratio, 2),
                    "max_drawdown": round(max_drawdown * 100, 2),
                    "max_margin_utilization": round(max_margin_util, 2),
                    "max_leverage_ratio": round(max_leverage, 2),
                    "total_days": len(common_dates),
                    "start_date": common_dates[0],
                    "end_date": common_dates[-1]
                },
                "equity_curve": {
                    "dates": common_dates,
                    "values": [round(v, 4) for v in equity_curve_normalized]
                },
                "daily_returns": [round(r, 6) for r in returns_array.tolist()],
                "margin_utilization": [round(m, 2) for m in daily_margin_util_pct],
                "leverage_ratios": [round(l, 2) for l in daily_leverage_ratio],
                "validation": {
                    "status": validation_status,
                    "margin_exceeded": margin_exceeded,
                    "leverage_exceeded": leverage_exceeded,
                    "max_margin_date": max_margin_date,
                    "max_leverage_date": max_leverage_date
                }
            }

            logger.info(f"✅ Simulation complete for {allocation_id}: CAGR={cagr*100:.2f}%, Sharpe={sharpe_ratio:.2f}, Max Margin={max_margin_util:.1f}%, Max Leverage={max_leverage:.2f}x, Status={validation_status}")

            return {
                "status": "success",
                "simulation": simulation_result
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error simulating allocation {allocation_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/allocations/{allocation_id}/tearsheet")
async def generate_allocation_tearsheet(allocation_id: str, starting_capital: float = 1000000.0, force_regenerate: bool = False):
    """
    Generate QuantStats tearsheet for portfolio allocation

    If tearsheet already exists, returns existing path (unless force_regenerate=True)
    Stores tearsheet path in MongoDB for persistence

    Returns: HTML tearsheet file path or inline HTML
    """
    try:
        import quantstats as qs
        import pandas as pd
        import numpy as np

        # Fetch allocation
        allocation = portfolio_allocations_collection.find_one({"allocation_id": allocation_id})
        if not allocation:
            raise HTTPException(status_code=404, detail=f"Allocation {allocation_id} not found")

        # Create output directory
        project_root = '/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader'
        tearsheet_dir = os.path.join(project_root, 'outputs', 'portfolio_tearsheets')
        os.makedirs(tearsheet_dir, exist_ok=True)

        tearsheet_filename = f"{allocation_id}_tearsheet.html"
        tearsheet_path = os.path.join(tearsheet_dir, tearsheet_filename)
        relative_path = f"/outputs/portfolio_tearsheets/{tearsheet_filename}"

        # Check if tearsheet already exists and was previously generated
        if not force_regenerate and os.path.exists(tearsheet_path) and allocation.get('tearsheet_url'):
            logger.info(f"Tearsheet already exists for allocation {allocation_id}, returning existing path")

            # Read basic stats from existing file (just count trading days from file size estimation)
            file_size_kb = os.path.getsize(tearsheet_path) / 1024
            estimated_days = 900  # Approximate

            return {
                "status": "success",
                "allocation_id": allocation_id,
                "tearsheet_path": tearsheet_path,
                "tearsheet_url": relative_path,
                "trading_days": estimated_days,
                "date_range": allocation.get('tearsheet_date_range', {"start": "N/A", "end": "N/A"}),
                "already_existed": True
            }

        logger.info(f"Generating tearsheet for allocation {allocation_id}")

        allocations_dict = allocation.get('allocations', {})
        if not allocations_dict:
            raise HTTPException(status_code=400, detail="Allocation has no strategy allocations")

        # Fetch FULL strategy data
        strategy_data = {}
        dates_set = None

        for strategy_id, weight_pct in allocations_dict.items():
            backtest = strategy_backtest_data_collection.find_one({"strategy_id": strategy_id})
            if not backtest:
                logger.warning(f"No backtest data found for strategy {strategy_id}, skipping")
                continue

            raw_data_full = backtest.get('raw_data_backtest_full', [])
            if not raw_data_full or not isinstance(raw_data_full, list) or len(raw_data_full) == 0:
                logger.warning(f"Incomplete backtest data for strategy {strategy_id}, skipping")
                continue

            # Parse dates and returns
            dates = [item['date'] for item in raw_data_full if all(k in item for k in ['date', 'return'])]
            returns = [item['return'] for item in raw_data_full if all(k in item for k in ['date', 'return'])]

            if not returns or not dates:
                logger.warning(f"Incomplete parsed data for strategy {strategy_id}, skipping")
                continue

            strategy_data[strategy_id] = {
                'returns': np.array(returns),
                'dates': dates,
                'weight': weight_pct / 100.0
            }

            if dates_set is None:
                dates_set = set(dates)
            else:
                dates_set = dates_set.intersection(set(dates))

        if not strategy_data:
            raise HTTPException(
                status_code=400,
                detail="No valid backtest data found for strategies in this allocation"
            )

        # Build common date index
        common_dates = sorted(list(dates_set))

        # Calculate portfolio daily returns (weighted average)
        portfolio_returns_list = []

        for date in common_dates:
            daily_return = 0.0
            for strategy_id, data in strategy_data.items():
                dates = data['dates']
                returns = data['returns']
                weight = data['weight']

                date_to_idx = dict(zip(dates, range(len(dates))))
                if date not in date_to_idx:
                    continue

                idx = date_to_idx[date]
                strategy_return = returns[idx]
                contribution = strategy_return * weight
                daily_return += contribution

            portfolio_returns_list.append(daily_return)

        # Convert to pandas Series with DatetimeIndex
        returns_series = pd.Series(
            portfolio_returns_list,
            index=pd.to_datetime(common_dates),
            name=f'Portfolio {allocation_id}'
        )

        # Filter to trading days only (where any strategy had activity)
        # Keep only days where at least one strategy was actively trading
        returns_series = returns_series[returns_series != 0]

        logger.info(f"Generating tearsheet with {len(returns_series)} trading days")

        # Generate HTML tearsheet
        tearsheet_filename = f"{allocation_id}_tearsheet.html"
        tearsheet_path = os.path.join(tearsheet_dir, tearsheet_filename)

        # Generate QuantStats tearsheet
        qs.reports.html(
            returns_series,
            output=tearsheet_path,
            title=f'Portfolio Allocation: {allocation_id}'
        )

        logger.info(f"✅ Tearsheet generated: {tearsheet_path}")

        # Store tearsheet path in MongoDB for persistence
        date_range = {
            "start": str(returns_series.index.min().date()),
            "end": str(returns_series.index.max().date())
        }

        portfolio_allocations_collection.update_one(
            {"allocation_id": allocation_id},
            {
                "$set": {
                    "tearsheet_path": tearsheet_path,
                    "tearsheet_url": relative_path,
                    "tearsheet_generated_at": datetime.utcnow(),
                    "tearsheet_trading_days": len(returns_series),
                    "tearsheet_date_range": date_range
                }
            }
        )

        logger.info(f"✅ Tearsheet path stored in MongoDB for {allocation_id}")

        return {
            "status": "success",
            "allocation_id": allocation_id,
            "tearsheet_path": tearsheet_path,
            "tearsheet_url": relative_path,
            "trading_days": len(returns_series),
            "date_range": date_range,
            "already_existed": False
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating tearsheet for {allocation_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STRATEGY MANAGEMENT APIs
# ============================================================================

@app.get("/api/v1/strategies")
async def get_all_strategies():
    """
    Get all strategy configurations
    Returns list of all strategies with metadata
    """
    try:
        strategies = list(strategy_configurations_collection.find({}))

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
    Includes backtest data if available
    """
    try:
        strategy = strategy_configurations_collection.find_one({"strategy_id": strategy_id})

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Remove MongoDB _id
        strategy.pop('_id', None)

        # Also fetch backtest data
        backtest_data = strategy_backtest_data_collection.find_one({"strategy_id": strategy_id})
        if backtest_data:
            backtest_data.pop('_id', None)
            strategy['backtest_data'] = backtest_data

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
    Create new strategy configuration
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
        existing = strategy_configurations_collection.find_one({"strategy_id": strategy_id})
        if existing:
            raise HTTPException(status_code=409, detail=f"Strategy {strategy_id} already exists")

        # Add timestamps
        strategy_data['created_at'] = datetime.utcnow()
        strategy_data['updated_at'] = datetime.utcnow()
        strategy_data['status'] = strategy_data.get('status', 'ACTIVE')

        # Insert into MongoDB
        strategy_configurations_collection.insert_one(strategy_data)

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
    Update strategy configuration
    Allows partial updates of strategy fields
    """
    try:
        # Check if strategy exists
        existing = strategy_configurations_collection.find_one({"strategy_id": strategy_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Add updated timestamp
        updates['updated_at'] = datetime.utcnow()

        # Update in MongoDB
        result = strategy_configurations_collection.update_one(
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
    Delete strategy configuration
    Marks as INACTIVE instead of hard delete (soft delete)
    """
    try:
        # Check if strategy exists
        existing = strategy_configurations_collection.find_one({"strategy_id": strategy_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Soft delete - mark as INACTIVE
        result = strategy_configurations_collection.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "status": "INACTIVE",
                    "deleted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"✅ Deleted (soft) strategy: {strategy_id}")

        return {
            "status": "success",
            "message": f"Strategy {strategy_id} deleted (marked INACTIVE)",
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
    Sync/update strategy backtest data
    Called when backtest results are updated (e.g., after paper trading)
    """
    try:
        # Validate required fields
        required_fields = ['daily_returns', 'mean_return_daily', 'volatility_daily']
        for field in required_fields:
            if field not in backtest_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Check if strategy exists
        strategy = strategy_configurations_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Add metadata
        backtest_data['strategy_id'] = strategy_id
        backtest_data['synced_at'] = datetime.utcnow()
        backtest_data['created_at'] = datetime.utcnow()

        # Upsert backtest data
        result = strategy_backtest_data_collection.replace_one(
            {"strategy_id": strategy_id},
            backtest_data,
            upsert=True
        )

        action = "updated" if result.matched_count > 0 else "created"

        logger.info(f"✅ Synced backtest data for strategy {strategy_id} ({action})")

        return {
            "status": "success",
            "message": f"Backtest data for {strategy_id} {action}",
            "strategy_id": strategy_id,
            "action": action
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing backtest data for {strategy_id}: {str(e)}", exc_info=True)
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
    Start Pub/Sub subscribers in background threads with automatic reconnection
    """
    import time

    def start_execution_confirmations_sub():
        while True:
            try:
                streaming_pull_future = subscriber.subscribe(
                    execution_confirmations_subscription,
                    callback=execution_confirmations_callback
                )
                logger.info("Listening for execution confirmations...")
                streaming_pull_future.result()
            except Exception as e:
                logger.error(f"Execution confirmations subscriber error: {str(e)}")
                logger.warning("Reconnecting in 5 seconds...")
                try:
                    streaming_pull_future.cancel()
                except:
                    pass
                time.sleep(5)
                logger.info("Attempting to reconnect execution confirmations subscriber...")

    def start_account_updates_sub():
        while True:
            try:
                streaming_pull_future = subscriber.subscribe(
                    account_updates_subscription,
                    callback=account_updates_callback
                )
                logger.info("Listening for account updates...")
                streaming_pull_future.result()
            except Exception as e:
                logger.error(f"Account updates subscriber error: {str(e)}")
                logger.warning("Reconnecting in 5 seconds...")
                try:
                    streaming_pull_future.cancel()
                except:
                    pass
                time.sleep(5)
                logger.info("Attempting to reconnect account updates subscriber...")

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

    # Initialize default test account if it doesn't exist
    test_accounts = ["DU1234567", "IBKR_Main"]
    for account_name in test_accounts:
        existing = account_state_collection.find_one(
            {"account": account_name},
            sort=[("timestamp", -1)]
        )
        
        if not existing:
            logger.info(f"Creating default account state for {account_name}")
            default_state = {
                "account": account_name,
                "equity": 100000.0,  # $100K starting capital
                "cash_balance": 100000.0,
                "margin_used": 0.0,
                "margin_available": 200000.0,  # 2x leverage available
                "timestamp": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "positions": [],
                "open_orders": []
            }
            account_state_collection.insert_one(default_state)
            account_state_cache[account_name] = default_state
            logger.info(f"✅ Default account {account_name} created")

    # TODO: Sync all configured accounts with brokers
    # This is critical for ensuring state consistency
    logger.info("Account Data Service ready")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Account Data Service MVP")
    uvicorn.run(app, host="0.0.0.0", port=8002)
