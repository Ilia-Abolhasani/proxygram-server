from flask import Blueprint, jsonify, current_app
from app.controller.job_controller import JobController


from flask import Blueprint, jsonify, request

blueprint = Blueprint("job", __name__)


@blueprint.route("/fetch_new_proxy", methods=["GET"])
def post_log():
    context = current_app.config["context"]
    telegram_api = current_app.config["telegram_api"]
    logger_api = current_app.config["logger_api"]
    job_controller = JobController(context, telegram_api, logger_api)
    result = job_controller.fetch_new_proxies()
    return jsonify(result), 200
