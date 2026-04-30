from flask import Blueprint, jsonify

from app.db import check_connection

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    error = check_connection()

    if error:
        return jsonify({"status": "error", "database": "unavailable", "detail": error}), 503

    return jsonify({"status": "ok", "database": "ok"})
