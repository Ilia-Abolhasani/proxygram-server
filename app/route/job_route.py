from flask import Blueprint, jsonify, request

from app.cron.job_queue import job_queue
from app.cron import manager

blueprint = Blueprint("job", __name__)


# HTTP status per queue outcome.
_STATUS_CODE = {
    "ran": 200,
    "submitted": 202,
    "unknown_job": 404,
    "running": 409,
    "already_queued": 409,
    "too_early": 409,
    "timed_out": 504,
    "failed": 500,
}


def _run_response(name):
    """Run a job and return its result.

    Calling this endpoint means "do it now", so the job runs as part of this
    request and the response carries what it actually returned -- it is not
    handed to the background queue. min_interval is not consulted: that gate
    is there to stop the *scheduler* running a job ahead of its cron period,
    not to overrule someone asking by hand.

    ?queue=true instead drops it on the background queue and returns straight
    away, for when you do not want to wait for the result.
    """
    if request.args.get("queue", "").lower() == "true":
        accepted, reason, detail = job_queue.submit(name, force=True)
        body = {"job": name, "status": reason, "message": detail}
        return jsonify(body), _STATUS_CODE.get(reason, 409)

    ok, reason, detail, result = job_queue.run_now(name)
    body = {"job": name, "status": reason, "message": detail}
    if result is not None:
        body["result"] = result
    return jsonify(body), _STATUS_CODE.get(reason, 500)


@blueprint.route("/fetch_new_proxy", methods=["GET"])
def fetch_new_proxy():
    return _run_response(manager.FETCH_NEW_PROXIES)


@blueprint.route("/edit_channel_message", methods=["GET"])
def edit_channel_message():
    return _run_response(manager.EDIT_CHANNEL_MESSAGE)


@blueprint.route("/status", methods=["GET"])
def status():
    return jsonify(job_queue.status()), 200
