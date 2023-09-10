import sys
import logging
from flask import Flask
from app.cron.manager import start_jobs
from app.Context import Context
from app.middleware.request_handler import request_handler_middleware
from app.route import route_bp
from app.util.Telegram import Telegram
from app.util.BotAPI import BotAPI
from app.util.LoggerBot import LoggerBot
from app.config.config import Config


def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


setup_logging(level=logging.ERROR)

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Uncaught')


def custom_excepthook(exctype, value, traceback):
    logger.error("Uncaught error.", exc_info=(exctype, value, traceback))


# sys.excepthook = custom_excepthook

app = Flask(__name__)
app.register_blueprint(route_bp)
app.before_request(request_handler_middleware)

# Initialize
context = Context()
telegram_api = Telegram(
    Config.telegram_app_id,
    Config.telegram_app_hash,
    Config.telegram_phone,
    Config.database_encryption_key,
    Config.tdlib_directory
)
telegram_api.remove_all_proxies()
bot_api = BotAPI()
logger_api = LoggerBot()

start_jobs(context, telegram_api, bot_api, logger_api)
