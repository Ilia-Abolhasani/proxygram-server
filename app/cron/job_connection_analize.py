import time
from app.cron import job_lock
from app.config.config import Config


def start(context, logger_api):
    global job_lock
    with job_lock:
        print("job_connection_analize")
        try:
            start_time = time.time()
            context.proxies_connection_update()
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"proxies_connection_update elapsed_time: {elapsed_time}")

            start_time = time.time()
            context.delete_dead_proxies(
                Config.dead_proxies_threshold_number,
                Config.dead_proxies_threshold_ping,
            )
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"delete_dead_proxies elapsed_time: {elapsed_time}")
        except Exception as error:
            logger_api.announce(error, "Connection analized job.")
