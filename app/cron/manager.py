from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config.config import Config
import requests
import app.cron.job_channel_add_message as job_channel_add_message
import app.cron.job_channel_edit_message as job_channel_edit_message
import app.cron.job_connection_analize as job_connection_analize

import app.cron.job_fetch_new_proxies as job_fetch_new_proxies
import app.cron.job_cleanup_reports as job_cleanup_reports
import app.cron.job_add_csv_report as job_add_csv_report


def call_fetch_new_proxies():
    try:
        url = f"http://127.0.0.1:{Config.server_port}/api/job/fetch_new_proxy"
        print(f"[Scheduler] Calling {url}")
        res = requests.get(url, timeout=60)
        if res.status_code == 200:
            print(f"[Scheduler] ✅ fetch_new_proxy executed successfully")
            if "message" in res:
                print(res["message"])
        else:
            print(f"[Scheduler] ⚠️ fetch_new_proxy failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"[Scheduler] ❌ Error calling fetch_new_proxy: {e}")


def start_jobs(context, bot_api, logger_api):
    scheduler = BackgroundScheduler({"apscheduler.job_defaults.max_instances": 6})
    job_fetch_new_proxies.start(context, logger_api)
    job_connection_analize.start(context, logger_api)
    job_channel_edit_message.start(context, bot_api, logger_api)
    # job_add_csv_report.start(context, bot_api, logger_api)
    # job_channel_add_message.start(context, bot_api, logger_api)

    # scheduler.add_job(
    #     lambda: job_add_csv_report.start(context, bot_api, logger_api),
    #     trigger=CronTrigger.from_crontab("0 0 * * *"),
    # )

    # job add message to channel
    scheduler.add_job(
        lambda: job_channel_add_message.start(context, bot_api, logger_api),
        trigger=CronTrigger.from_crontab("0 */4 * * *"),
    )

    # job edit last message of channel
    scheduler.add_job(
        lambda: job_channel_edit_message.start(context, bot_api, logger_api),
        trigger=CronTrigger.from_crontab("*/5 * * * *"),
    )

    # job test connection of proxy base on reports
    scheduler.add_job(
        lambda: job_connection_analize.start(context, logger_api),
        trigger=CronTrigger.from_crontab("*/6 * * * *"),
    )

    # job test connection of proxy base on reports
    scheduler.add_job(
        lambda: job_cleanup_reports.start(context, logger_api),
        trigger=CronTrigger.from_crontab("*/15 * * * *"),
    )

    # job fetch new proxies from other proxy chaneels
    scheduler.add_job(
        lambda: call_fetch_new_proxies(),
        trigger=CronTrigger.from_crontab("*/5 * * * *"),
    )
    scheduler.start()
