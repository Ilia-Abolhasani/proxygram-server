from flask import Blueprint, jsonify, request

from app.cron.job_queue import job_queue
from app.cron import manager

blueprint = Blueprint("job", __name__)


def _submit_response(name):
    """Queue a job and report what the queue decided.

    These routes used to run the job on the web thread, which is what let a
    slow TDLib call hang the server. They now return immediately: 202 when the
    job was queued, 409 when the queue refused it.
    """
    force = request.args.get("force", "").lower() == "true"
    accepted, reason, detail = job_queue.submit(name, force=force)
    body = {"job": name, "status": reason, "message": detail}
    if accepted:
        return jsonify(body), 202
    if reason == "unknown_job":
        return jsonify(body), 404
    return jsonify(body), 409


@blueprint.route("/fetch_new_proxy", methods=["GET"])
def fetch_new_proxy():
    return _submit_response(manager.FETCH_NEW_PROXIES)


@blueprint.route("/edit_channel_message", methods=["GET"])
def edit_channel_message():
    return _submit_response(manager.EDIT_CHANNEL_MESSAGE)


@blueprint.route("/status", methods=["GET"])
def status():
    return jsonify(job_queue.status()), 200
