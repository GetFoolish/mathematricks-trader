"""
MongoDB Schema Setup for Dashboard System
Creates collections and indexes for dashboards and widget_data
"""
import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_dashboard_collections():
    """Create collections and indexes for dashboard system"""
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client['mathematricks_trading']

        logger.info("Setting up dashboard collections and indexes...")

        # Create dashboards collection
        if 'dashboards' not in db.list_collection_names():
            db.create_collection('dashboards')
            logger.info("✅ Created 'dashboards' collection")
        else:
            logger.info("'dashboards' collection already exists")

        # Create indexes for dashboards
        dashboards = db['dashboards']
        dashboards.create_index([('dashboard_id', ASCENDING)], unique=True)
        dashboards.create_index([('created_by', ASCENDING), ('created_at', DESCENDING)])
        dashboards.create_index([('fund_id', ASCENDING)])
        logger.info("✅ Created indexes for 'dashboards' collection")

        # Create widget_data collection
        if 'widget_data' not in db.list_collection_names():
            db.create_collection('widget_data')
            logger.info("✅ Created 'widget_data' collection")
        else:
            logger.info("'widget_data' collection already exists")

        # Create indexes for widget_data
        widget_data = db['widget_data']
        widget_data.create_index([
            ('widget_type', ASCENDING),
            ('fund_id', ASCENDING),
            ('filters_hash', ASCENDING)
        ], unique=True)
        widget_data.create_index([('computed_at', ASCENDING)])
        # TTL index to auto-delete stale data after 24 hours
        widget_data.create_index([('created_at', ASCENDING)], expireAfterSeconds=86400)
        logger.info("✅ Created indexes for 'widget_data' collection")

        # Create a default dashboard for testing
        existing_dashboard = dashboards.find_one({'dashboard_id': 'default-dashboard-1'})
        if not existing_dashboard:
            default_dashboard = {
                'dashboard_id': 'default-dashboard-1',
                'name': 'Default Dashboard',
                'description': 'Default dashboard with fund balances and bank statement',
                'created_by': 'system',
                'fund_id': None,  # Shows all funds
                'is_locked': False,
                'widgets': [
                    {
                        'widget_id': 'widget-fund-balances-1',
                        'widget_type': 'FundBalances',
                        'position': {'x': 0, 'y': 0, 'w': 6, 'h': 4},
                        'config': {}
                    },
                    {
                        'widget_id': 'widget-bank-statement-1',
                        'widget_type': 'BankStatement',
                        'position': {'x': 6, 'y': 0, 'w': 6, 'h': 4},
                        'config': {
                            'date_range_days': 30,
                            'group_by': 'date'
                        }
                    }
                ],
                'grid_config': {'cols': 12, 'row_height': 100},
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            dashboards.insert_one(default_dashboard)
            logger.info("✅ Created default dashboard")
        else:
            logger.info("Default dashboard already exists")

        logger.info("✅ Dashboard schema setup complete!")

    except Exception as e:
        logger.error(f"Error setting up dashboard collections: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    setup_dashboard_collections()
