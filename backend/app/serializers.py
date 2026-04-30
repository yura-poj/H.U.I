def serialize_level(level: dict) -> dict:
    return {
        "id": level["id"],
        "order": level["order_index"],
        "title": level["title"],
        "description": level["description"],
        "monster": {
            "name": level["monster_name"],
            "icon": level["monster_icon"],
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
    }


def serialize_game(game: dict) -> dict:
    return {
        "id": game["id"],
        "level_id": game["level_id"],
        "status": game["status"],
        "monster": {
            "name": game["monster_name"],
            "icon": game["monster_icon"],
            "hp": game["monster_hp"],
            "max_hp": game["monster_max_hp"],
        },
        "rules": {
            "min_words_per_insult": game["min_words_per_insult"],
        },
    }
