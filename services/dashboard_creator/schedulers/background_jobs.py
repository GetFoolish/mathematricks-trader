"""
Background Jobs Scheduler
Uses APScheduler to run dashboard generation jobs in the background
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pymongo import MongoClient
from generators.client_dashboard import generate_client_dashboard
from generators.signal_sender_dashboard import generate_all_signal_sender_dashboards

logger = logging.getLogger(__name__)


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

    scheduler.start()

    logger.info("Background scheduler started")
    logger.info("  • Client dashboard: every 5 minutes")
    logger.info("  • Signal sender dashboards: every 1 minute")

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
