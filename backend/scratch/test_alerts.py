"""
test_alerts.py — Executable integration verification script.
Simulates a database state, triggers the background check worker,
and verifies database logging.
"""

import sys
import os
import asyncio

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import db
from worker import run_alert_check_cycle

async def main():
    print("[INFO] Triggering integration test for Alert Notification System...")
    
    # 1. Fetch active users to ensure database connectivity is working
    try:
        users = db.get_active_users()
        print("db access functional. Found " + str(len(users)) + " active patients with locations.")
        for u in users:
            print("  - Patient: " + str(u.get('name')) + " | Threshold: " + str(u.get('alert_threshold', 100)) + " | Phone: " + str(u.get('phone')) + " | Email: " + str(u.get('email')))
    except Exception as exc:
        print("db connection failed: " + str(exc))
        return

    # 2. Trigger the check cycle
    print("\nRunning complete Alert Check Cycle...")
    results = await run_alert_check_cycle()
    print("\nCycle complete. Results: " + str(results))

    # 3. Read back from logs to verify DB persistence
    print("\nReading back recent notifications from public.alerts_log...")
    if users:
        test_user = users[0]["id"]
        logs = db.get_user_alerts_log(test_user, limit=5)
        print("Found " + str(len(logs)) + " entries in alerts_log for user " + str(users[0]['name']) + ":")
        for log in logs:
            print("  - Channel: " + str(log.get('channel')) + " | Tier: " + str(log.get('alert_tier')) + " | Status: " + str(log.get('status')) + " | Sent at: " + str(log.get('sent_at')))
    else:
        print("No users found to retrieve alert logs for.")

if __name__ == "__main__":
    asyncio.run(main())
