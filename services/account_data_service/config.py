"""
Configuration for Account Data Service
"""
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'mathematricks_trading'

# GCP
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'mathematricks-trader')

# Polling
POLL_INTERVAL_SECONDS = int(os.getenv('ACCOUNT_POLL_INTERVAL', '300'))  # 5 minutes default

# Service
PORT = int(os.getenv('ACCOUNT_DATA_SERVICE_PORT', '8082'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
