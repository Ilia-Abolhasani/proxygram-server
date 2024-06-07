import hashlib
from flask import abort, request, jsonify, make_response
from app.Context import Context
from datetime import datetime, timezone

context = Context()


def request_handler_middleware():
    # Exclude the test_route from middleware
    if request.path == "/favicon.ico":
        return None
    if request.endpoint == "route.test_route":
        return None
    if not request.view_args:
        abort(404)
    agent_id = request.view_args.get("agent_id")
    agent = context.get_agent(agent_id)
    if not agent:
        abort(403)
    request_time = request.headers.get("X-Request-Time")
    hashed_timestamp = request.headers.get("X-Hashed-Timestamp")

    # Check if request_time and hashed_timestamp are present in the headers
    if not request_time or not hashed_timestamp:
        response = jsonify({"error": "Missing required headers."})
        return make_response(response, 400)

    # Calculate the hash of the received time
    message = f"{request_time}{agent.encrypted_key}"
    calculated_hash = hashlib.sha256(message.encode()).hexdigest()

    # Check if the calculated hash matches the received hashed_timestamp
    if calculated_hash != hashed_timestamp:
        response = jsonify({"error": "Hash mismatch."})
        return make_response(response, 400)

    # Convert the received time string to a datetime object
    received_time = datetime.strptime(request_time, "%Y-%m-%d %H:%M:%S")
    received_time = received_time.replace(tzinfo=timezone.utc)
    # Calculate the time difference
    current_time = datetime.now(timezone.utc)
    time_difference = current_time - received_time
    # Check if the time difference is less than 1 minute (60 seconds)
    if time_difference.total_seconds() > 60:
        response = jsonify({"error": "Request time exceeds 1 minute."})
        return make_response(response, 400)

    return None
