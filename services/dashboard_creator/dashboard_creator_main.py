#!/usr/bin/env python3
"""
DashboardCreatorService
Generates pre-computed dashboard JSONs for clients and strategy developers

Port: 8004
"""
import os
import logging
import uvicorn
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pymongo import MongoClient
from dotenv import load_dotenv

# Import dashboard generators
from generators.client_dashboard import generate_client_dashboard
from generators.signal_sender_dashboard import generate_signal_sender_dashboard
from generators.fund_balances_widget import generate_fund_balances_widget
from generators.account_statement_widget import generate_account_statement_widget

# Import scheduler
from schedulers.background_jobs import start_scheduler, stop_scheduler, widget_update_events

# Strategy Developer API has been migrated to mathematricks-website/netlify/functions/

# Load environment variables
load_dotenv()

# Logging setup
custom_formatter = logging.Formatter('|%(levelname)s|%(message)s|%(asctime)s|file:%(filename)s:line No.%(lineno)d')

# Console handler (no file logging in Docker)
console_handler = logging.StreamHandler()
console_handler.setFormatter(custom_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler]
)
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']

# Background scheduler (global)
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)"""
    global scheduler

    # Startup
    logger.info("Starting DashboardCreatorService on port 8004")
    logger.info(f"MongoDB connected: {MONGODB_URI[:50]}...")

    # Generate initial dashboards
    logger.info("Generating initial dashboards...")
    try:
        generate_client_dashboard(mongo_client)
        logger.info("✓ Client dashboard generated")
    except Exception as e:
        logger.error(f"Failed to generate client dashboard: {e}")

    # Start background scheduler
    scheduler = start_scheduler(mongo_client)

    yield

    # Shutdown
    logger.info("Shutting down DashboardCreatorService...")
    if scheduler:
        stop_scheduler(scheduler)
    mongo_client.close()
    logger.info("MongoDB connection closed")


# Create FastAPI app
app = FastAPI(
    title="DashboardCreatorService",
    description="Generates pre-computed dashboard JSONs for mathematricks.fund",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# DASHBOARD JSON ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "DashboardCreatorService",
        "version": "1.0.0",
        "mongodb_connected": mongo_client is not None,
        "scheduler_running": scheduler is not None and scheduler.running if scheduler else False
    }


@app.get("/api/v1/dashboards/client")
async def get_client_dashboard():
    """
    Get latest client dashboard JSON.

    Returns pre-computed dashboard from MongoDB (generated every 5 minutes).
    """
    try:
        dashboard = db['dashboard_snapshots'].find_one(
            {"dashboard_type": "client"}
        )

        if not dashboard:
            # Generate on-demand if not found
            logger.warning("Client dashboard not found in cache, generating...")
            dashboard = generate_client_dashboard(mongo_client)

        # Remove MongoDB _id and updated_at fields
        if "_id" in dashboard:
            del dashboard["_id"]
        if "updated_at" in dashboard:
            del dashboard["updated_at"]

        return JSONResponse(content=dashboard)

    except Exception as e:
        logger.error(f"Error retrieving client dashboard: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to retrieve client dashboard"}
        )


@app.get("/api/v1/dashboards/signal-sender/{strategy_id}")
async def get_signal_sender_dashboard(strategy_id: str):
    """
    Get latest signal sender dashboard JSON for a specific strategy.

    Args:
        strategy_id: Strategy identifier

    Returns pre-computed dashboard from MongoDB (generated every 1 minute).
    """
    try:
        dashboard = db['dashboard_snapshots'].find_one({
            "dashboard_type": "signal_sender",
            "strategy_id": strategy_id
        })

        if not dashboard:
            # Generate on-demand if not found
            logger.warning(f"Dashboard for {strategy_id} not found in cache, generating...")
            dashboard = generate_signal_sender_dashboard(strategy_id, mongo_client)

        # Remove MongoDB _id and updated_at fields
        if "_id" in dashboard:
            del dashboard["_id"]
        if "updated_at" in dashboard:
            del dashboard["updated_at"]

        return JSONResponse(content=dashboard)

    except Exception as e:
        logger.error(f"Error retrieving dashboard for {strategy_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve dashboard for {strategy_id}"}
        )


@app.post("/api/v1/dashboards/regenerate")
async def regenerate_dashboards():
    """
    Force regeneration of all dashboards.

    Useful for testing or when immediate update is needed.
    """
    try:
        # Generate client dashboard
        client_dashboard = generate_client_dashboard(mongo_client)

        # Generate all signal sender dashboards
        strategies = list(db['strategy_configurations'].find({"status": "ACTIVE"}))
        sender_count = 0
        for strategy in strategies:
            try:
                generate_signal_sender_dashboard(strategy["strategy_id"], mongo_client)
                sender_count += 1
            except Exception as e:
                logger.error(f"Failed to generate dashboard for {strategy['strategy_id']}: {e}")

        return {
            "status": "success",
            "client_dashboard": "regenerated",
            "signal_sender_dashboards": f"{sender_count} regenerated"
        }

    except Exception as e:
        logger.error(f"Error regenerating dashboards: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to regenerate dashboards"}
        )


# ============================================================================
# WIDGET ENDPOINTS (v5 Dashboard System)
# ============================================================================

@app.get("/api/v1/widgets/events")
async def widget_updates_stream(request: Request):
    """
    SSE (Server-Sent Events) endpoint for real-time widget updates.

    Sends events when widget data is regenerated by the background scheduler.
    Frontend clients connect to this endpoint to receive real-time updates.
    """
    async def event_generator():
        last_event_index = 0
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected")
                    break

                # Send new events
                if last_event_index < len(widget_update_events):
                    for event in widget_update_events[last_event_index:]:
                        yield f"data: {json.dumps(event)}\n\n"
                    last_event_index = len(widget_update_events)

                # Keep connection alive with heartbeat
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled")
        except Exception as e:
            logger.error(f"SSE error: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/api/v1/widgets/{widget_type}/generate")
async def generate_widget_on_demand(widget_type: str, request: dict = None):
    """
    Force regeneration of a specific widget type.

    Called by the reload button in the frontend to fetch fresh data immediately.

    Args:
        widget_type: "FundBalances" or "BankStatement"
        request: Optional filters (fund_id, account_filter, date_range_days, etc.)
    """
    try:
        if request is None:
            request = {}

        fund_id = request.get('fund_id')

        if widget_type == "FundBalances":
            data = generate_fund_balances_widget(mongo_client, fund_id)
            return {"status": "success", "data": data}

        elif widget_type == "AccountStatement":
            account_filter = request.get('account_filter')
            date_range_days = request.get('date_range_days', 30)
            group_by = request.get('group_by', 'date')

            data = generate_account_statement_widget(
                mongo_client,
                fund_id=fund_id,
                account_filter=account_filter,
                date_range_days=date_range_days,
                group_by=group_by
            )
            return {"status": "success", "data": data}

        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown widget type: {widget_type}"}
            )

    except Exception as e:
        logger.error(f"Error generating widget {widget_type}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate widget: {str(e)}"}
        )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "dashboard_creator_main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info"
    )
