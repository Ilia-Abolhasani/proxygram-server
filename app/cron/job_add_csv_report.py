from app.util.Message import create_message
from app.config.config import Config
from app.action.csv_report import create_csv_report
import time


message_caption = """
لیست کامل تمام پروکسی‌های فعال و متصل تلگرام 🚀

این لیست شامل: آدرس پروکسی، میانگین سرعت دانلود پروکسی‌ها، میانگین پینگ پروکسی‌ها و... 
برای تهیه این لیست بیشتر از 100 کانال پروکسی بررسی شده است.

پروکسی‌گرام، تنها مرجع کامل پروکسی‌های تلگرام می‌باشد و تمام پروکسی‌ها را از نظر سرعت بررسی می‌کند.
🆔 @mtprotoAI
"""


def start(context, bot_api, logger_api):
    # No lock: the job queue's single worker is what serialises jobs now.
    print("job_add_csv_report")
    try:
        path = "./report.csv"
        create_csv_report(context, path, 500)
        result = bot_api.send_document(path, "proxies_report.csv", message_caption)
    except Exception as error:
        logger_api.announce(error, "Add csv report to channel job.")
