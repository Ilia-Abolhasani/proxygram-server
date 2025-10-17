import sys
import logging
from flask import Flask
from proxies_tg_wrapper.api_wrapper import Telegram_API
from app.config.config import Config
from app.cron.manager import start_jobs
from app.Context import Context
from app.middleware.request_handler import request_handler_middleware
from app.route import route_bp
from app.util.BotAPI import BotAPI
from app.middleware import error_handler


## log & exception
def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    root.addHandler(ch)


setup_logging(level=logging.ERROR)

logging.basicConfig(
    level=logging.ERROR, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Uncaught")


def custom_excepthook(exctype, value, traceback):
    logger.error("Uncaught error.", exc_info=(exctype, value, traceback))


sys.excepthook = custom_excepthook

if __name__ == "__main__":
    # Initialize
    app = Flask(__name__)
    app.register_blueprint(route_bp)
    app.before_request(request_handler_middleware)
    error_handler.register_error_handlers(app)

    context = Context()
    telegram_api = Telegram_API(
        Config.telegram_app_id,
        Config.telegram_app_hash,
        Config.telegram_phone,
        Config.database_encryption_key,
        Config.tdlib_directory,
        Config.tdlib_lib_path,
    )
    telegram_api.remove_all_proxies()
    bot_api = BotAPI(Config.bot_api_key, Config.bot_chat_id)
    logger_api = BotAPI(Config.logger_bot_api_key, Config.logger_bot_chat_id)

    app.config["context"] = context
    app.config["telegram_api"] = telegram_api
    app.config["bot_api"] = bot_api
    app.config["logger_api"] = logger_api

    start_jobs(context, telegram_api, bot_api, logger_api)

    app.run(debug=False, host="0.0.0.0", port=Config.server_port)
