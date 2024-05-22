from app.cron import job_lock


def start(context, logger_api):
    global job_lock
    with job_lock:
        print("job_cleanup_reports")
        try:
            context.cleanup_old_ping_reports()            
        except Exception as error:
            logger_api.announce(error, "job_cleanup_reports.")
