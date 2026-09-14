from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from forge.config import settings
from forge.loop import sync_and_learn
from forge.store import list_published_jobs

logger = logging.getLogger("contentforge.scheduler")

_scheduler: BackgroundScheduler | None = None


def _sync_all() -> None:
    for job in list_published_jobs():
        job_id = job["id"]
        try:
            row = sync_and_learn(job_id)
            logger.info("sync %s -> view=%s", job_id, row["view"])
        except Exception as e:  # noqa: BLE001
            logger.warning("sync %s failed: %s", job_id, e)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    if not getattr(settings, "scheduler_enabled", False):
        logger.info("scheduler disabled")
        return
    s = BackgroundScheduler(timezone="Asia/Shanghai")
    s.add_job(_sync_all, "interval", minutes=getattr(settings, "scheduler_interval_minutes", 60),
              id="metrics_sync", max_instances=1, coalesce=True)
    s.start()
    _scheduler = s
    logger.info("scheduler started every %s min", settings.scheduler_interval_minutes)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
