#!/usr/bin/env python3
"""
Automatic Alert Scheduler
Runs background alert checks every 2 hours for all active users.
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime

from worker import run_alert_check_cycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scheduled_alert_check():
    """Wrapper function to run the alert check cycle."""
    try:
        logger.info(f"🕐 Starting scheduled alert check at {datetime.now()}")
        results = await run_alert_check_cycle()
        logger.info(f"✅ Scheduled check completed: {results}")
    except Exception as e:
        logger.error(f"❌ Scheduled alert check failed: {e}")

def run_scheduler():
    """Run the scheduled alert checks."""
    # Schedule alert checks every 2 hours
    schedule.every(2).hours.do(lambda: asyncio.run(scheduled_alert_check()))
    
    logger.info("🚀 Alert scheduler started - checking every 2 hours")
    
    # Run immediately on startup
    asyncio.run(scheduled_alert_check())
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute for scheduled tasks

if __name__ == "__main__":
    run_scheduler()