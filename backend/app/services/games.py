from typing import Any

from app.services.insults import count_words, monster_reply, normalize_insult, score_insult


def submit_insult_attempt(user: dict, game_id: str, text: str) -> dict[str, Any]:
    game = _get_game_for_user(game_id, user["id"])

    if not game:
        return {"status": "game_not_found"}

    if game["status"] != "active":
        return {"status": "game_already_finished", "game": game}

    if game["level_id"] != user["current_level_id"]:
        return {"status": "stale_game_session", "game": game}

    actual_words = count_words(text)
    required_words = game["min_words_per_insult"]

    if actual_words < required_words:
        return {
            "status": "too_few_words",
            "accepted": False,
            "reason": "min_words",
            "required_words": required_words,
            "actual_words": actual_words,
            "damage": 0,
            "monster_reply": "The monster waits for a sharper insult.",
            "game": game,
        }

    score = score_insult(text)
    damage = score["damage"]
    result = _apply_current_insult_damage(
        game_id=game["id"],
        user_id=user["id"],
        level_id=game["level_id"],
        original_text=text,
        normalized_text=normalize_insult(text),
        damage=damage,
        score_metadata=score,
    )

    if result["status"] == "duplicate_insult":
        return {
            "status": "duplicate_insult",
            "accepted": False,
            "reason": "duplicate_insult",
            "damage": 0,
            "monster_reply": "The monster has already heard that one.",
            "game": result.get("game", game),
        }

    if result["status"] in {"game_already_finished", "stale_game_session", "game_not_found"}:
        return result

    full_game = result["game"]
    advanced_user = result.get("advanced_user")

    return {
        "status": "accepted",
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
        "advanced_to_level_id": (
            advanced_user["current_level_id"] if advanced_user else None
        ),
        "advanced_to_monster_hp": (
            advanced_user["current_monster_hp"] if advanced_user else None
        ),
        "game": full_game,
    }


def _get_game_for_user(game_id: str, user_id: str) -> dict | None:
    from app.repositories import get_game_for_user

    return get_game_for_user(game_id, user_id)


def _apply_current_insult_damage(**kwargs) -> dict:
    from app.repositories import apply_current_insult_damage

    return apply_current_insult_damage(**kwargs)
