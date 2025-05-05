import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    server_port = os.getenv("server_port")
    database_name = os.getenv("database_name")
    database_user = os.getenv("database_user")
    database_pass = os.getenv("database_pass")
    database_host = os.getenv("database_host")
    database_port = os.getenv("database_port")
    telegram_app_id = os.getenv("telegram_app_id")
    telegram_app_hash = os.getenv("telegram_app_hash")
    telegram_phone = os.getenv("telegram_phone")
    database_encryption_key = os.getenv("database_encryption_key")
    tdlib_directory = os.getenv("tdlib_directory")
    tdlib_lib_path = os.getenv("tdlib_lib_path")
    # main chanel bot
    bot_api_key = os.getenv("bot_api_key")
    bot_chat_id = os.getenv("bot_chat_id")
    # logger
    logger_bot_api_key = os.getenv("logger_bot_api_key")
    logger_bot_chat_id = os.getenv("logger_bot_chat_id")

    # Context parameters
    session_retry_max = 5
    session_retry_interval = 3

    max_report_ping = 30
    max_report_speed = 10
    max_timeouts = 5
    successful_pings = 5

    # proxie selection parameters
    message_limit_proxy = 5
    max_ping_value = 10000
    exponential_decay = 0.9
    contribute_history = 5
    ping_score_weight = 0.6
    speed_score_weight = 0.4

    # dead proxies
    dead_proxies_threshold_number = 10
    dead_proxies_threshold_ping = 250
