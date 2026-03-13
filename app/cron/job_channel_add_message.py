from app.util.Message import create_message, create_message_iran
from app.cron import job_lock
from app.config.config import Config
from app.action.top_proxies import get_top_proxies
import time


def start(context, bot_api, logger_api):
    global job_lock
    with job_lock:
        print("job_channel_add_message")
        try:
            connect_num = context.count_connect_proxies()
            total = context.count_total_proxies()
            channels_num = context.count_channels()

            # پیام عادی (همه پروکسی‌ها)
            proxies = get_top_proxies(context, Config.message_limit_proxy)
            message = create_message(proxies, connect_num, total, channels_num)
            result = bot_api.send_message(message)
            message_id = result.message_id
            context.add_or_update_setting("last_sent_message_id", message_id)

            time.sleep(2)

            # پیام سرورهای ایران
            proxies_ir = get_top_proxies(
                context, Config.message_limit_proxy, country="IR"
            )
            if proxies_ir:
                message_ir = create_message_iran(
                    proxies_ir, connect_num, total, channels_num
                )
                result_ir = bot_api.send_message(message_ir)
                context.add_or_update_setting(
                    "last_sent_message_id_ir", result_ir.message_id
                )
        except Exception as error:
            logger_api.announce(error, "Add message to channel job.")
