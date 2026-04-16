#!/usr/bin/env python3
"""
排程器：每週一到週五 19:00 執行 check_broker.py
"""

import time
import subprocess
from datetime import datetime

HOUR = 19
MINUTE = 0


def should_run(now):
    """週一到週五 19:00"""
    return now.weekday() < 5 and now.hour == HOUR and now.minute == MINUTE


def main():
    print(f"排程啟動：每週一到週五 {HOUR:02d}:{MINUTE:02d}")
    last_run_date = None

    while True:
        now = datetime.now()
        today = now.date()

        if should_run(now) and last_run_date != today:
            print(f"\n[{now}] 執行 check_broker.py ...")
            result = subprocess.run(
                ["python3", "check_broker.py"],
                capture_output=True, text=True, timeout=120,
            )
            print(result.stdout)
            if result.stderr:
                print(f"STDERR: {result.stderr}")
            last_run_date = today
            print(f"[{datetime.now()}] 完成，等待下一次執行")

        time.sleep(30)


if __name__ == "__main__":
    main()
