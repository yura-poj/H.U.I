from flask import Blueprint, current_app, jsonify, request

from app.auth import current_user_required
from app.repositories import (
    create_game,
    get_game_for_user,
    get_level,
)
from app.serializers import serialize_game
from app.services.games import submit_insult_attempt

games_bp = Blueprint("games", __name__)


@games_bp.post("/games")
@current_user_required
def start_game(user):
    level = get_level(user["current_level_id"])

    if not level:
        return jsonify({"error": "current_level_not_found"}), 500

    game = create_game(
        user_id=user["id"],
        level=level,
        monster_hp=user.get("current_monster_hp", level["monster_hp"]),
    )
    full_game = get_game_for_user(game["id"], user["id"])

    return jsonify({"game": serialize_game(full_game)}), 201


@games_bp.get("/games/<game_id>")
@current_user_required
def get_game(user, game_id):
    game = get_game_for_user(game_id, user["id"])

    if not game:
        return jsonify({"error": "game_not_found"}), 404

    return jsonify({"game": serialize_game(game)})


@games_bp.post("/games/<game_id>/insults")
@current_user_required
def submit_insult(user, game_id):
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()

    if not text:
        return jsonify({"error": "insult_required"}), 400

    if len(text) > current_app.config.get("MAX_INSULT_LENGTH", 1000):
        return jsonify({"error": "insult_too_long"}), 400

    result = submit_insult_attempt(user, game_id, text)

    if result["status"] == "game_not_found":
        return jsonify({"error": "game_not_found"}), 404

    if result["status"] == "game_already_finished":
        return jsonify(
            {"error": "game_already_finished", "game": serialize_game(result["game"])}
        ), 409

    if result["status"] == "stale_game_session":
        return jsonify(
            {
                "accepted": False,
                "reason": "stale_game_session",
                "damage": 0,
                "error": "stale_game_session",
                "game": serialize_game(result["game"]),
            }
        ), 409

    return jsonify(_serialize_insult_result(result))


def _serialize_insult_result(result: dict) -> dict:
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"status", "game"}
    }
    payload["game"] = serialize_game(result["game"])
    return payload
