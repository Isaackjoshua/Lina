"""Scheduled jobs. Run with: python -m lina.worker

One long-running process with cron-style triggers in East Africa Time.
Jobs are added per milestone:
  M2/M3  pipeline        04:00 daily
  M5     expiry          00:15 daily
  M6     digests         07:00 daily (weekly digest on Mondays)
  M7     social          configurable, after review
"""

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from lina.config import get_settings

log = logging.getLogger("lina.worker")


def heartbeat() -> None:
    log.info("worker alive")


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(heartbeat, CronTrigger(minute=0), id="heartbeat")
    return scheduler


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    scheduler = build_scheduler()
    log.info(
        "worker started, timezone=%s, jobs=%s",
        settings.timezone,
        [j.id for j in scheduler.get_jobs()],
    )
    scheduler.start()


if __name__ == "__main__":
    main()
