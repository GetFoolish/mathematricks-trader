#!/usr/bin/env python3
"""
DashboardCreatorService
Generates pre-computed dashboard JSONs for clients and strategy developers

Port: 8004
"""
import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from dotenv import load_dotenv

# Import dashboard generators
from generators.client_dashboard import generate_client_dashboard
from generators.signal_sender_dashboard import generate_signal_sender_dashboard

# Import scheduler
from schedulers.background_jobs import start_scheduler, stop_scheduler

# Import API router
from api.strategy_developer_api import router as strategy_dev_router, set_mongo_client

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../../logs/dashboard_creator.log'),
        logging.StreamHandler()
    ]
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

    # Set MongoDB client for API module
    set_mongo_client(mongo_client)

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
# STRATEGY DEVELOPER API
# ============================================================================

# Include strategy developer API routes
app.include_router(strategy_dev_router)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info"
    )
