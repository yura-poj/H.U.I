from functools import wraps

from flask import jsonify, request

from app.repositories import find_user_by_token


def current_user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "authentication_required"}), 401

        token = auth_header.removeprefix("Bearer ").strip()
        user = find_user_by_token(token)

        if not user:
            return jsonify({"error": "invalid_token"}), 401

        return view(user, *args, **kwargs)

    return wrapped
