"""Scheduled jobs. Run with: python -m lina.worker

One long-running process with cron-style triggers in East Africa Time.
Jobs are added per milestone:
  M3     pipeline        04:00 daily (scheduled)
  M5     expiry          00:15 daily
  M6     digests         07:00 daily (weekly digest on Mondays)
  M7     social          configurable, after review
"""

import argparse
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from lina.config import get_settings
from lina.pipeline.__main__ import run_command

log = logging.getLogger("lina.worker")


def daily_pipeline() -> None:
    """04:00 EAT: fetch verified sources and fill the review queue. Never raises, so one bad
    night cannot stop the scheduler."""
    try:
        code = run_command(argparse.Namespace(command="run", source=None))
        log.info("daily pipeline finished with exit code %s", code)
    except Exception:
        log.exception("daily pipeline crashed")


def heartbeat() -> None:
    log.info("worker alive")


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(heartbeat, CronTrigger(minute=0), id="heartbeat")
    scheduler.add_job(daily_pipeline, CronTrigger(hour=4, minute=0), id="pipeline")
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
