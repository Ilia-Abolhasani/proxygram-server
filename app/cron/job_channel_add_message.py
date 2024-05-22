from app.util.Message import create_message
from app.cron import job_lock
from app.config.config import Config
from app.action.top_proxies import get_top_proxies
import time


def start(context, bot_api, logger_api):
    global job_lock
    with job_lock:
        print("job_channel_add_message")
        try:
            proxies = get_top_proxies(context, Config.message_limit_proxy)
            connect_num = context.count_connect_proxies()
            total = context.count_total_proxies()
            channels_num = context.count_channels()
            message = create_message(proxies, connect_num, total, channels_num)
            result = bot_api.send_message(message)
            message_id = result.message_id
            context.add_or_update_setting("last_sent_message_id", message_id)
        except Exception as error:
            logger_api.announce(error, "Add message to channel job.")
