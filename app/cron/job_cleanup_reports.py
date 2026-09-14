import time


def start(context, logger_api):
    # No lock: the job queue's single worker is what serialises jobs now.
    print("job_cleanup_reports")
    try:
        start_time = time.time()
        context.cleanup_old_ping_reports()
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"job_cleanup_reports elapsed_time: {elapsed_time}")
    except Exception as error:
        logger_api.announce(error, "job_cleanup_reports.")
