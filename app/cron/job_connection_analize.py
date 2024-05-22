import time
from app.cron import job_lock


def start(context, logger_api):
    global job_lock
    with job_lock:
        print("job_connection_analize")
        try:
            start_time = time.time()
            context.proxies_connection_update()            
            context.delete_dead_proxies(30)
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"job_connection_analize elapsed_time: {elapsed_time}")
        except Exception as error:
            logger_api.announce(error, "Connection analized job.")
