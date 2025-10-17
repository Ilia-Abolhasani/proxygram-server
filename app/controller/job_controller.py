from app.cron import job_fetch_new_proxies


class JobController:
    def __init__(self, context, logger_api):
        self.context = context
        self.logger_api = logger_api

    def fetch_new_proxies(self):
        result = job_fetch_new_proxies.fetch(self.context, self.logger_api)
        return {"status": "ok", "message": result}
