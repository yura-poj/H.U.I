from flask import Blueprint, current_app, jsonify

from app.db import check_connection

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    error = check_connection()

    if error:
        current_app.logger.warning("Database health check failed: %s", error)
        return jsonify({"status": "error", "database": "unavailable"}), 503

    return jsonify({"status": "ok", "database": "ok"})
