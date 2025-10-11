"""
Signal Ingestion Service - MVP
Receives raw signals and converts them to standardized Mathematricks format.
Integrates with existing signal_collector.py at line 350-359.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request
from google.cloud import pubsub_v1
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader/logs/signal_ingestion_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Signal Ingestion Service", version="1.0.0-MVP")

# Initialize Google Cloud Pub/Sub Publisher
project_id = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, 'standardized-signals')

# Initialize MongoDB
mongo_uri = os.getenv('MONGODB_URI')
mongo_client = MongoClient(mongo_uri)
db = mongo_client['mathematricks_trading']
raw_signals_collection = db['raw_signals']
standardized_signals_collection = db['standardized_signals']


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "signal_ingestion_service", "version": "1.0.0-MVP"}


@app.post("/webhook/tradingview")
async def receive_tradingview_signal(request: Request):
    """
    Receive raw signal from TradingView webhook
    This is the MVP implementation for ONE signal provider
    """
    try:
        raw_data = await request.json()
        logger.info(f"Received TradingView signal: {raw_data}")

        # Store raw signal
        raw_signal_doc = {
            "timestamp": datetime.utcnow(),
            "source": "tradingview",
            "raw_data": raw_data,
            "processed": False,
            "created_at": datetime.utcnow()
        }
        raw_signals_collection.insert_one(raw_signal_doc)

        # Convert to standardized format
        standardized_signal = convert_tradingview_to_mathematricks(raw_data)

        # Store standardized signal
        standardized_signals_collection.insert_one(standardized_signal)

        # Publish to Pub/Sub for CerebroService
        message_data = str(standardized_signal).encode('utf-8')
        future = publisher.publish(topic_path, message_data)
        message_id = future.result()

        logger.info(f"Published signal {standardized_signal['signal_id']} to Pub/Sub: {message_id}")

        return {
            "status": "success",
            "signal_id": standardized_signal['signal_id'],
            "message_id": message_id
        }

    except Exception as e:
        logger.error(f"Error processing signal: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def convert_tradingview_to_mathematricks(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert TradingView signal format to Mathematricks standard format
    MVP implementation - basic conversion for one provider
    """
    signal_id = f"TV_{datetime.utcnow().timestamp()}"

    # Extract fields from TradingView format
    # Adjust these based on your actual TradingView webhook format
    standardized = {
        "signal_id": signal_id,
        "strategy_id": raw_data.get('strategy', 'unknown'),
        "timestamp": datetime.utcnow(),
        "instrument": raw_data.get('ticker', ''),
        "direction": raw_data.get('direction', 'LONG').upper(),
        "action": raw_data.get('action', 'ENTRY').upper(),
        "order_type": raw_data.get('order_type', 'MARKET').upper(),
        "price": float(raw_data.get('price', 0)),
        "quantity": float(raw_data.get('quantity', 1)),
        "stop_loss": float(raw_data.get('stop_loss', 0)),
        "take_profit": float(raw_data.get('take_profit', 0)),
        "expiry": raw_data.get('expiry'),
        "metadata": {
            "expected_alpha": raw_data.get('expected_alpha', 0),
            "backtest_data": raw_data.get('backtest_data', {})
        },
        "processed_by_cerebro": False,
        "created_at": datetime.utcnow()
    }

    logger.info(f"Standardized signal: {signal_id} for {standardized['instrument']}")
    return standardized


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Signal Ingestion Service MVP")
    uvicorn.run(app, host="0.0.0.0", port=8001)
