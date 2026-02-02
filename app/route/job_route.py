from flask import Blueprint, jsonify, current_app
from app.controller.job_controller import JobController
import app.cron.job_channel_edit_message as job_channel_edit_message


from flask import Blueprint, jsonify, request

blueprint = Blueprint("job", __name__)


@blueprint.route("/fetch_new_proxy", methods=["GET"])
def post_log():
    context = current_app.config["context"]
    logger_api = current_app.config["logger_api"]
    job_controller = JobController(context, logger_api)
    result = job_controller.fetch_new_proxies()
    return jsonify(result), 200


@blueprint.route("/edit_channel_message", methods=["GET"])
def edit_channel_message():
    context = current_app.config["context"]
    bot_api = current_app.config["bot_api"]
    logger_api = current_app.config["logger_api"]
    job_channel_edit_message.start(context, bot_api, logger_api)
    return jsonify({"message": "edit_channel_message executed successfully"}), 200
