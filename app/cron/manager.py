from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config.config import Config
import app.cron.job_channel_add_message as job_channel_add_message
import app.cron.job_channel_edit_message as job_channel_edit_message
import app.cron.job_connection_analize as job_connection_analize

import app.cron.job_fetch_new_proxies as job_fetch_new_proxies
import app.cron.job_cleanup_reports as job_cleanup_reports
import app.cron.job_add_csv_report as job_add_csv_report

from app.cron.job_queue import job_queue

# Job names, also the keys used by /api/job/* and the status endpoint.
FETCH_NEW_PROXIES = "fetch_new_proxies"
EDIT_CHANNEL_MESSAGE = "edit_channel_message"
ADD_CHANNEL_MESSAGE = "add_channel_message"
CONNECTION_ANALIZE = "connection_analize"
CLEANUP_REPORTS = "cleanup_reports"
ADD_CSV_REPORT = "add_csv_report"

MINUTE = 60


def _submit(name):
    """Hand a job to the queue and log why it was turned away.

    The scheduler fires on a fixed cron, but the queue decides whether the job
    actually runs: a firing that arrives while the previous one is still going,
    or before the job's min_interval has elapsed, is dropped here.
    """
    accepted, reason, detail = job_queue.submit(name)
    if not accepted:
        print(f"[Scheduler] {name} not queued ({reason}): {detail}")
    return accepted


def start_jobs(context, bot_api, logger_api):
    # min_interval mirrors each job's cron period, so a manual /api/job/* call
    # cannot make a job run ahead of its normal schedule. timeout keeps one
    # stuck run (TDLib in particular) from stalling the whole queue.
    job_queue.register(
        FETCH_NEW_PROXIES,
        lambda: job_fetch_new_proxies.start(context, logger_api),
        min_interval=5 * MINUTE,
        timeout=10 * MINUTE,
    )
    job_queue.register(
        EDIT_CHANNEL_MESSAGE,
        lambda: job_channel_edit_message.start(context, bot_api, logger_api),
        min_interval=5 * MINUTE,
        timeout=5 * MINUTE,
    )
    job_queue.register(
        ADD_CHANNEL_MESSAGE,
        lambda: job_channel_add_message.start(context, bot_api, logger_api),
        min_interval=6 * 60 * MINUTE,
        timeout=5 * MINUTE,
    )
    job_queue.register(
        CONNECTION_ANALIZE,
        lambda: job_connection_analize.start(context, logger_api),
        min_interval=6 * MINUTE,
        timeout=10 * MINUTE,
    )
    job_queue.register(
        CLEANUP_REPORTS,
        lambda: job_cleanup_reports.start(context, logger_api),
        min_interval=15 * MINUTE,
        timeout=10 * MINUTE,
    )
    job_queue.register(
        ADD_CSV_REPORT,
        lambda: job_add_csv_report.start(context, bot_api, logger_api),
        min_interval=24 * 60 * MINUTE,
        timeout=10 * MINUTE,
    )

    job_queue.start()

    # Startup jobs go through the queue too, so they run one after another on
    # the worker instead of blocking Flask's start-up on this thread.
    job_queue.submit(FETCH_NEW_PROXIES)
    job_queue.submit(CONNECTION_ANALIZE)

    # max_instances is 1: a firing that overlaps the previous run is dropped by
    # APScheduler, and the queue's dedupe catches whatever slips past.
    scheduler = BackgroundScheduler(
        {
            "apscheduler.job_defaults.max_instances": 1,
            "apscheduler.job_defaults.coalesce": True,
        }
    )

    # job add message to channel
    scheduler.add_job(
        lambda: _submit(ADD_CHANNEL_MESSAGE),
        trigger=CronTrigger.from_crontab("0 */6 * * *"),
    )

    # job edit last message of channel
    scheduler.add_job(
        lambda: _submit(EDIT_CHANNEL_MESSAGE),
        trigger=CronTrigger.from_crontab("*/5 * * * *"),
    )

    # job test connection of proxy base on reports
    scheduler.add_job(
        lambda: _submit(CONNECTION_ANALIZE),
        trigger=CronTrigger.from_crontab("*/6 * * * *"),
    )

    # job cleanup old reports
    scheduler.add_job(
        lambda: _submit(CLEANUP_REPORTS),
        trigger=CronTrigger.from_crontab("*/15 * * * *"),
    )

    # job fetch new proxies from other proxy chaneels
    scheduler.add_job(
        lambda: _submit(FETCH_NEW_PROXIES),
        trigger=CronTrigger.from_crontab("*/5 * * * *"),
    )
    scheduler.start()
