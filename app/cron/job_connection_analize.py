from app.cron import job_lock


def start(context, logger_api):
    global job_lock
    with job_lock:
        print("job_connection_analize")
        try:
            context.proxies_connection_update()            
            context.delete_dead_proxies(30)
        except Exception as error:
            logger_api.announce(error, "Connection analized job.")
