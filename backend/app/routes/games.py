from flask import Blueprint, jsonify, request

from app.auth import current_user_required
from app.repositories import (
    advance_user_level_if_possible,
    apply_insult_damage,
    create_game,
    get_game_for_user,
    get_level,
    has_used_insult,
)
from app.serializers import serialize_game
from app.services.insults import count_words, monster_reply, normalize_insult, score_insult

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

    game = get_game_for_user(game_id, user["id"])

    if not game:
        return jsonify({"error": "game_not_found"}), 404

    if game["status"] != "active":
        return jsonify({"error": "game_already_finished", "game": serialize_game(game)}), 409

    actual_words = count_words(text)
    required_words = game["min_words_per_insult"]

    if actual_words < required_words:
        return jsonify(
            {
                "accepted": False,
                "reason": "min_words",
                "required_words": required_words,
                "actual_words": actual_words,
                "damage": 0,
                "monster_reply": "The monster waits for a sharper insult.",
                "game": serialize_game(game),
            }
        )

    normalized_text = normalize_insult(text)

    if has_used_insult(user["id"], normalized_text):
        return jsonify(
            {
                "accepted": False,
                "reason": "duplicate_insult",
                "damage": 0,
                "monster_reply": "The monster has already heard that one.",
                "game": serialize_game(game),
            }
        )

    score = score_insult(text)
    damage = score["damage"]
    updated_game = apply_insult_damage(
        game_id=game["id"],
        user_id=user["id"],
        level_id=game["level_id"],
        original_text=text,
        normalized_text=normalized_text,
        damage=damage,
        score_metadata=score,
    )

    full_game = get_game_for_user(updated_game["id"], user["id"])
    advanced_to_level_id = None
    advanced_to_monster_hp = None

    if full_game["status"] == "won":
        advanced_user = advance_user_level_if_possible(user["id"], full_game["level_id"])
        if advanced_user:
            advanced_to_level_id = advanced_user["current_level_id"]
            advanced_to_monster_hp = advanced_user["current_monster_hp"]

    return jsonify(
        {
            "accepted": True,
            "damage": damage,
            "score": {
                "source": score["source"],
                "toxic": score["toxic"],
                "toxicity_score": score["toxicity_score"],
                "label": score["label"],
                "signals": score["signals"],
            },
            "monster_reply": monster_reply(damage, full_game["status"] == "won"),
            "advanced_to_level_id": advanced_to_level_id,
            "advanced_to_monster_hp": advanced_to_monster_hp,
            "game": serialize_game(full_game),
        }
    )
