from app.util.Message import create_message, create_message_iran
from app.cron import job_lock
from app.config.config import Config
from app.action.top_proxies import get_top_proxies


def start(context, bot_api, logger_api):
    global job_lock
    with job_lock:
        print("job_channel_edit_message")
        try:
            connect_num = context.count_connect_proxies()
            total = context.count_total_proxies()
            channels_num = context.count_channels()

            # ویرایش پیام عادی
            setting = context.get_setting("last_sent_message_id")
            if setting:
                message_id = int(setting.value)
                proxies = get_top_proxies(context, Config.message_limit_proxy)
                message = create_message(proxies, connect_num, total, channels_num)
                try:
                    bot_api.edit_message_text(message, message_id)
                except Exception:
                    pass

            # ویرایش پیام سرورهای ایران
            setting_ir = context.get_setting("last_sent_message_id_ir")
            if setting_ir:
                message_id_ir = int(setting_ir.value)
                proxies_ir = get_top_proxies(context, Config.message_limit_proxy, country="IR")
                if proxies_ir:
                    message_ir = create_message_iran(proxies_ir, connect_num, total, channels_num)
                    try:
                        bot_api.edit_message_text(message_ir, message_id_ir)
                    except Exception:
                        pass
        except Exception as error:
            logger_api.announce(error, "Edit message to channel job.")
