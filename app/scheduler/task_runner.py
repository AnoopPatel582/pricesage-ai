import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.tracker_service import TrackerService

logger = logging.getLogger("pricesage.scheduler")
scheduler = BackgroundScheduler()


def start_scheduler(check_interval_seconds: int = 60):
    if not scheduler.running:
        scheduler.add_job(
            func=TrackerService.check_all_tracked_products,
            trigger=IntervalTrigger(seconds=check_interval_seconds),
            id="periodic_price_checker",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Price checks scheduled every %s seconds", check_interval_seconds)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
