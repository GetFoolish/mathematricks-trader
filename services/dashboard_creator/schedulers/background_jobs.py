"""
Background Jobs Scheduler
Uses APScheduler to run dashboard generation jobs in the background
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pymongo import MongoClient
from generators.client_dashboard import generate_client_dashboard
from generators.signal_sender_dashboard import generate_all_signal_sender_dashboards
from generators.fund_balances_widget import generate_fund_balances_widget
from generators.account_statement_widget import generate_account_statement_widget
from generators.system_health_widget import generate_system_health_widget

logger = logging.getLogger(__name__)

# Global event bus for SSE (in-memory, can be replaced with Redis for multi-instance)
widget_update_events = []


def emit_widget_update_event(event_data: dict):
    """
    Emit widget update event to all SSE subscribers

    Args:
        event_data: Dictionary with widget_type, fund_id, timestamp
    """
    widget_update_events.append(event_data)
    # Keep only last 100 events to avoid memory issues
    if len(widget_update_events) > 100:
        widget_update_events.pop(0)


def generate_all_widget_data(mongo_client: MongoClient):
    """
    Generate all widget data for active funds and emit SSE events

    This function is called by the scheduler every 30 seconds to regenerate
    widget data for all active funds.
    """
    try:
        db = mongo_client['mathematricks_trading']
        funds = list(db['funds'].find({"status": "ACTIVE"}))

        logger.info(f"Generating widget data for {len(funds)} active funds...")

        for fund in funds:
            fund_id = fund["fund_id"]

            try:
                # Generate FundBalances widget for this fund
                generate_fund_balances_widget(mongo_client, fund_id)
                emit_widget_update_event({
                    "widget_type": "FundBalances",
                    "fund_id": fund_id,
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Generate AccountStatement widget for this fund (30 days, grouped by date)
                generate_account_statement_widget(
                    mongo_client,
                    fund_id=fund_id,
                    date_range_days=30,
                    group_by="date"
                )
                emit_widget_update_event({
                    "widget_type": "AccountStatement",
                    "fund_id": fund_id,
                    "timestamp": datetime.utcnow().isoformat()
                })

            except Exception as e:
                logger.error(f"Failed to generate widgets for fund {fund_id}: {e}")

        # Also generate widgets for all funds combined (fund_id=None)
        try:
            generate_fund_balances_widget(mongo_client, fund_id=None)
            emit_widget_update_event({
                "widget_type": "FundBalances",
                "fund_id": None,
                "timestamp": datetime.utcnow().isoformat()
            })

            generate_account_statement_widget(
                mongo_client,
                fund_id=None,
                date_range_days=30,
                group_by="date"
            )
            emit_widget_update_event({
                "widget_type": "AccountStatement",
                "fund_id": None,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Generate system health widget (refreshed every 30s)
            generate_system_health_widget(mongo_client, fund_id=None)
            emit_widget_update_event({
                "widget_type": "SystemHealth",
                "fund_id": None,
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Failed to generate combined widgets: {e}")

        logger.info(f"✅ Widget data generation complete")

    except Exception as e:
        logger.error(f"Error in generate_all_widget_data: {e}", exc_info=True)


def start_scheduler(mongo_client: MongoClient) -> BackgroundScheduler:
    """
    Start background scheduler for dashboard generation.

    Args:
        mongo_client: MongoDB client instance (passed to generator functions)

    Returns:
        BackgroundScheduler instance (already started)
    """
    scheduler = BackgroundScheduler()

    # Generate client dashboard every 5 minutes
    scheduler.add_job(
        func=lambda: generate_client_dashboard(mongo_client),
        trigger=IntervalTrigger(minutes=5),
        id='client_dashboard',
        name='Generate Client Dashboard',
        replace_existing=True
    )

    # Generate signal sender dashboards every 1 minute
    scheduler.add_job(
        func=lambda: generate_all_signal_sender_dashboards(mongo_client),
        trigger=IntervalTrigger(minutes=1),
        id='signal_sender_dashboards',
        name='Generate Signal Sender Dashboards',
        replace_existing=True
    )

    # Generate widget data every 30 seconds
    scheduler.add_job(
        func=lambda: generate_all_widget_data(mongo_client),
        trigger=IntervalTrigger(seconds=30),
        id='widget_data_generator',
        name='Generate Widget Data',
        replace_existing=True
    )

    scheduler.start()

    logger.info("Background scheduler started")
    logger.info("  • Client dashboard: every 5 minutes")
    logger.info("  • Signal sender dashboards: every 1 minute")
    logger.info("  • Widget data: every 30 seconds")

    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler):
    """Stop the background scheduler"""
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")


if __name__ == "__main__":
    # Test the scheduler
    import os
    import time
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri)

    scheduler = start_scheduler(client)

    try:
        # Run for 10 seconds to test
        print("Scheduler running... Press Ctrl+C to stop")
        time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
    finally:
        stop_scheduler(scheduler)
