from psycopg.errors import UniqueViolation
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories import create_auth_token, create_user, find_user_by_username
from app.serializers import serialize_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/users/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    if len(username) < 3:
        return jsonify({"error": "username_too_short"}), 400

    if len(password) < 6:
        return jsonify({"error": "password_too_short"}), 400

    try:
        user = create_user(username, generate_password_hash(password))
    except UniqueViolation:
        return jsonify({"error": "username_taken"}), 409

    token = create_auth_token(user["id"])

    return jsonify({"user": serialize_user(user), "token": token}), 201


@auth_bp.post("/users/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    user = find_user_by_username(username)

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid_credentials"}), 401

    token = create_auth_token(user["id"])

    return jsonify({"user": serialize_user(user), "token": token})
