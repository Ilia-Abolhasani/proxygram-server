from app.util.Message import create_message
from app.cron import job_lock
from app.config.config import Config
from app.action.top_proxies import get_top_proxies


def start(context, bot_api, logger_api):
    global job_lock
    with job_lock:
        print("job_channel_edit_message")
        try:
            setting = context.get_setting("last_sent_message_id")
            if not setting:
                return
            message_id = int(setting.value)

            proxies = get_top_proxies(context, Config.message_limit_proxy)
            connect_num = context.count_connect_proxies()
            total = context.count_total_proxies()
            channels_num = context.count_channels()
            message = create_message(proxies, connect_num, total, channels_num)

            result = bot_api.edit_message_text(message, message_id)
        except Exception as error:
            logger_api.announce(error, "Edit message to channel job.")
