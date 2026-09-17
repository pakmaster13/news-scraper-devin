import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import RECAP_DAYS, RECAP_HOUR, RECAP_MINUTE, RECAP_TIMEZONE
from app.recap import generate_and_store

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _run_morning_recap() -> None:
    try:
        recap = await generate_and_store(deliver=True)
        logger.info("morning recap generated for %s", recap["recap_date"])
    except Exception:  # scheduler job must never die silently
        logger.exception("morning recap failed")


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = AsyncIOScheduler(timezone=RECAP_TIMEZONE)
    scheduler.add_job(
        _run_morning_recap,
        CronTrigger(
            day_of_week=RECAP_DAYS,
            hour=RECAP_HOUR,
            minute=RECAP_MINUTE,
            timezone=RECAP_TIMEZONE,
        ),
        id="morning_recap",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def next_run_time() -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job("morning_recap")
    return job.next_run_time.isoformat() if job and job.next_run_time else None
