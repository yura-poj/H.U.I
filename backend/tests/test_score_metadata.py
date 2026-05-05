from datetime import UTC, datetime

import pytest

from app.serializers import serialize_insult_history_item


def test_serialize_insult_history_item_includes_score_metadata():
    serialized = serialize_insult_history_item(
        {
            "id": "insult-1",
            "original_text": "ты вонючий болотный тапок",
            "damage": 6,
            "score_source": "model",
            "toxic": True,
            "toxicity_score": 0.891,
            "toxicity_label": "toxic",
            "model_signals": {"insult": 0.94},
            "level_id": "swamp_troll",
            "monster_name": "Slopjaw",
            "created_at": datetime(2026, 4, 30, 20, 27, tzinfo=UTC),
        }
    )

    assert serialized["score"] == {
        "source": "model",
        "toxic": True,
        "toxicity_score": 0.891,
        "label": "toxic",
        "signals": {"insult": 0.94},
    }


def test_submit_insult_returns_and_persists_model_score(monkeypatch):
    import app.services.games as games_service

    captured = {}

    game = {
        "id": "game-1",
        "user_id": "user-1",
        "level_id": "swamp_troll",
        "monster_hp": 94,
        "status": "active",
        "monster_name": "Slopjaw",
        "monster_icon": "/image.webp",
        "monster_max_hp": 100,
        "min_words_per_insult": 3,
    }
    score = {
        "damage": 6,
        "source": "model",
        "toxic": True,
        "toxicity_score": 0.891,
        "label": "toxic",
        "signals": {"insult": 0.94},
    }

    monkeypatch.setattr(games_service, "_get_game_for_user", lambda game_id, user_id: game)
    monkeypatch.setattr(games_service, "score_insult", lambda text: score)

    def fake_apply_insult_damage(**kwargs):
        captured.update(kwargs)
        return {"status": "accepted", "game": game, "advanced_user": None}

    monkeypatch.setattr(games_service, "_apply_current_insult_damage", fake_apply_insult_damage)

    payload = games_service.submit_insult_attempt(
        {"id": "user-1", "username": "player", "current_level_id": "swamp_troll"},
        "game-1",
        "ты вонючий болотный тапок",
    )

    assert payload["status"] == "accepted"
    assert payload["damage"] == 6
    assert payload["score"] == {
        "source": "model",
        "toxic": True,
        "toxicity_score": 0.891,
        "label": "toxic",
        "signals": {"insult": 0.94},
    }
    assert captured["damage"] == 6
    assert captured["score_metadata"] == score


def test_submit_insult_handles_duplicate_insert_race(monkeypatch):
    import app.services.games as games_service

    game = {
        "id": "game-1",
        "user_id": "user-1",
        "level_id": "level_1",
        "monster_hp": 20,
        "status": "active",
        "monster_name": "Monster 1",
        "monster_icon": "1.png",
        "monster_max_hp": 20,
        "min_words_per_insult": 1,
    }

    monkeypatch.setattr(games_service, "_get_game_for_user", lambda game_id, user_id: game)
    monkeypatch.setattr(
        games_service,
        "score_insult",
        lambda text: {
            "damage": 6,
            "source": "model",
            "toxic": False,
            "toxicity_score": 0.1,
            "label": "normal",
            "signals": {},
        },
    )
    monkeypatch.setattr(
        games_service,
        "_apply_current_insult_damage",
        lambda **kwargs: {"status": "duplicate_insult", "game": game},
    )

    payload = games_service.submit_insult_attempt(
        {"id": "user-1", "username": "player", "current_level_id": "level_1"},
        "game-1",
        "soggy boot",
    )

    assert payload["status"] == "duplicate_insult"
    assert payload["accepted"] is False
    assert payload["reason"] == "duplicate_insult"
    assert payload["damage"] == 0


def test_submit_insult_rejects_stale_game_session_before_scoring(monkeypatch):
    import app.services.games as games_service

    game = {
        "id": "game-1",
        "user_id": "user-1",
        "level_id": "level_1",
        "monster_hp": 0,
        "status": "active",
        "monster_name": "Monster 1",
        "monster_icon": "1.png",
        "monster_max_hp": 20,
        "min_words_per_insult": 1,
    }

    monkeypatch.setattr(games_service, "_get_game_for_user", lambda game_id, user_id: game)
    monkeypatch.setattr(
        games_service,
        "score_insult",
        lambda text: (_ for _ in ()).throw(AssertionError("stale games must not score")),
    )

    payload = games_service.submit_insult_attempt(
        {"id": "user-1", "username": "player", "current_level_id": "level_2"},
        "game-1",
        "soggy boot",
    )

    assert payload["status"] == "stale_game_session"
    assert payload["game"] == game
