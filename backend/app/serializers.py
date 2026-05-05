def _monster_icon_url(icon_file: str) -> str:
    if icon_file.startswith("/"):
        return icon_file

    return f"/{icon_file}"


def serialize_level(level: dict) -> dict:
    return {
        "id": level["id"],
        "order": level["order_index"],
        "title": level["title"],
        "description": level["description"],
        "monster": {
            "name": level["monster_name"],
            "icon": _monster_icon_url(level["monster_icon"]),
            "icon_file": level["monster_icon"],
        },
        "rules": {
            "hp": level["monster_hp"],
            "min_words_per_insult": level["min_words_per_insult"],
        },
    }


def serialize_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "current_level_id": user["current_level_id"],
        "current_monster_hp": user["current_monster_hp"],
    }


def serialize_game(game: dict) -> dict:
    return {
        "id": game["id"],
        "level_id": game["level_id"],
        "status": game["status"],
        "monster": {
            "name": game["monster_name"],
            "icon": _monster_icon_url(game["monster_icon"]),
            "icon_file": game["monster_icon"],
            "hp": game["monster_hp"],
            "max_hp": game["monster_max_hp"],
        },
        "rules": {
            "min_words_per_insult": game["min_words_per_insult"],
        },
    }


def serialize_insult_history_item(insult: dict) -> dict:
    return {
        "id": insult["id"],
        "text": insult["original_text"],
        "damage": insult["damage"],
        "score": {
            "source": insult["score_source"],
            "toxic": insult["toxic"],
            "toxicity_score": insult["toxicity_score"],
            "label": insult["toxicity_label"],
            "signals": insult["model_signals"] or {},
        },
        "level_id": insult["level_id"],
        "monster_name": insult["monster_name"],
        "created_at": insult["created_at"].isoformat(),
    }


def serialize_leaderboard_entry(entry: dict | None) -> dict | None:
    if not entry:
        return None

    return {
        "rank": entry["rank"],
        "username": entry["username"],
        "total_damage": entry["total_damage"],
        "insults_count": entry["insults_count"],
        "current_level_id": entry["current_level_id"],
    }
