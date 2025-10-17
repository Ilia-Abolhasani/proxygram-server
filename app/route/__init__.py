from app.route.proxy_route import blueprint as proxy_bp
from app.route.report_route import blueprint as report_bp
from app.route.log_route import blueprint as log_bp
from app.route.job_route import blueprint as job_bp
from flask import Blueprint, jsonify

route_bp = Blueprint("route", __name__)

route_bp.register_blueprint(proxy_bp, url_prefix="/api/<int:agent_id>/proxy")
route_bp.register_blueprint(report_bp, url_prefix="/api/<int:agent_id>/report")
route_bp.register_blueprint(log_bp, url_prefix="/api/<int:agent_id>/log")
route_bp.register_blueprint(job_bp, url_prefix="/api/job")


@route_bp.route("/api/test", methods=["GET"])
def test_route():
    return jsonify(message="successful"), 200
