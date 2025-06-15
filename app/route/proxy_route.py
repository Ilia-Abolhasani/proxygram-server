from flask import Blueprint, jsonify, request
from app.controller.proxy_controller import ProxyController

blueprint = Blueprint("proxy", __name__)
controller = ProxyController()


@blueprint.route("/speed", methods=["GET"])
def get_speed(agent_id):
    result = controller.get_proxies_speed(agent_id)
    result = jsonify(result)
    return result, 200


@blueprint.route("/ping", methods=["GET"])
def get_ping(agent_id):
    disconnect = request.args.get("disconnect")
    disconnect = disconnect.lower() == "true"
    result = controller.get_proxies_ping(agent_id, disconnect)
    result = jsonify(result)
    return result, 200


@blueprint.route("/delete/<int:proxy_id>", methods=["DELETE"])
def delete_proxies(agent_id, proxy_id):
    controller.delete_proxy(agent_id, proxy_id)
    return jsonify(True), 204


@blueprint.route("/delete/soft/<int:proxy_id>", methods=["DELETE"])
def soft_delete_proxies(agent_id, proxy_id):
    controller.soft_delete_proxy(agent_id, proxy_id)
    return jsonify(True), 204
