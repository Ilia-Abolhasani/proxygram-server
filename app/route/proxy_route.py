from flask import Blueprint, jsonify, request
from app.controller.proxy_controller import ProxyController

blueprint = Blueprint("proxy", __name__)
controller = ProxyController()


@blueprint.route("/speed", methods=["GET"])
def get_speed(agent_id):
    country = request.args.get("country")
    result = controller.get_proxies_speed(agent_id, country)
    result = jsonify(result)
    return result, 200


@blueprint.route("/ping", methods=["GET"])
def get_ping(agent_id):
    disconnect = request.args.get("disconnect")
    disconnect = disconnect.lower() == "true"
    country = request.args.get("country")
    result = controller.get_proxies_ping(agent_id, disconnect, country)
    result = jsonify(result)
    return result, 200


@blueprint.route("/delete/<int:proxy_id>", methods=["DELETE"])
def delete_proxies(agent_id, proxy_id):
    controller.delete_proxy(agent_id, proxy_id)
    return jsonify(True), 204


@blueprint.route("/delete/soft/<int:proxy_id>", methods=["DELETE"])
def soft_delete_proxy(agent_id, proxy_id):
    controller.soft_delete_proxy(agent_id, proxy_id)
    return jsonify(True), 204


@blueprint.route("/delete/soft", methods=["POST"])
def soft_delete_proxies(agent_id):
    body = request.get_json(silent=True) or {}
    proxy_ids = body.get("proxy_ids") or []
    if not isinstance(proxy_ids, list):
        return jsonify({"error": "proxy_ids must be a list."}), 400
    try:
        proxy_ids = [int(proxy_id) for proxy_id in proxy_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "proxy_ids must contain integers."}), 400
    deleted = controller.soft_delete_proxies(agent_id, proxy_ids)
    return jsonify({"deleted": deleted}), 200
