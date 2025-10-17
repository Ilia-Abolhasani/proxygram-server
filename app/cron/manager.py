from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import app.cron.job_channel_add_message as job_channel_add_message
import app.cron.job_channel_edit_message as job_channel_edit_message
import app.cron.job_connection_analize as job_connection_analize
import app.cron.job_fetch_new_proxies as job_fetch_new_proxies
import app.cron.job_cleanup_reports as job_cleanup_reports
import app.cron.job_add_csv_report as job_add_csv_report


def start_jobs(context, telegram_api, bot_api, logger_api):
    scheduler = BackgroundScheduler({"apscheduler.job_defaults.max_instances": 6})
    # job_fetch_new_proxies.start(context, telegram_api, logger_api)
    # job_connection_analize.start(context, logger_api)
    # job_channel_edit_message.start(context, bot_api, logger_api)
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
        lambda: job_fetch_new_proxies.start(context, telegram_api, logger_api),
        trigger=CronTrigger.from_crontab("*/1 * * * *"),
    )
    scheduler.start()
