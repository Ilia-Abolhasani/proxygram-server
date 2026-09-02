import threading
import time
import traceback
from flask import Flask
from flask import jsonify
from werkzeug.exceptions import HTTPException
from app.util.BotAPI import BotAPI
from app.config.config import Config

logger_bot = BotAPI(Config.logger_bot_api_key, Config.logger_bot_chat_id)

# One failing request used to produce one Telegram message. A scanner hitting
# the API is enough to flood the logger bot and burn its rate limit, so the
# announcements are throttled and the skipped ones are only counted.
_announce_lock = threading.Lock()
_announce_last = 0.0
_announce_skipped = 0


def _announce_throttled(error, prefix):
    global _announce_last, _announce_skipped
    with _announce_lock:
        now = time.monotonic()
        if now - _announce_last < Config.error_announce_min_interval:
            _announce_skipped += 1
            return
        skipped = _announce_skipped
        _announce_skipped = 0
        _announce_last = now
    if skipped:
        prefix = f"[{skipped} more error(s) suppressed] {prefix}"
    logger_bot.announce(error, prefix)


def register_error_handlers(app):
    app.register_error_handler(403, _access_denied_error)
    app.register_error_handler(404, _not_found_error)
    app.register_error_handler(500, _internal_error)
    app.register_error_handler(Exception, _handle_global_exception)


def _access_denied_error(error):
    return jsonify({"error": "Access denied."}), 403


def _not_found_error(error):
    return jsonify({"error": "Page not found."}), 404


def _internal_error(error):
    try:
        _announce_throttled(error, "Internal server error:")
    except Exception:
        return jsonify({"error": "Internal server error."}), 500
    return jsonify({"error": "Internal server error."}), 500


def _handle_global_exception(error):
    # 4xx are the client's fault and are not worth a Telegram message; without
    # this every abort(403)/abort(404) reached the announce path below.
    if isinstance(error, HTTPException):
        return jsonify({"error": error.name}), error.code
    try:
        _announce_throttled(error, "An error occurred:")
    except Exception:
        return jsonify({"error": "An error occurred, also for send."}), 500
    return jsonify({"error": "An error occurred."}), 500
