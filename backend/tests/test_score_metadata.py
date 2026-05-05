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
    flask = pytest.importorskip("flask")
    import app.auth as auth_module
    import app.routes.games as games_module
    from app.routes.games import games_bp

    app = flask.Flask(__name__)
    app.register_blueprint(games_bp, url_prefix="/api")
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

    monkeypatch.setattr(
        auth_module,
        "find_user_by_token",
        lambda token: {"id": "user-1", "username": "player", "current_level_id": "swamp_troll"},
    )
    monkeypatch.setattr(games_module, "get_game_for_user", lambda game_id, user_id: game)
    monkeypatch.setattr(games_module, "has_used_insult", lambda user_id, normalized_text: False)
    monkeypatch.setattr(games_module, "score_insult", lambda text: score)

    def fake_apply_insult_damage(**kwargs):
        captured.update(kwargs)
        return {"id": kwargs["game_id"]}

    monkeypatch.setattr(games_module, "apply_insult_damage", fake_apply_insult_damage)

    response = app.test_client().post(
        "/api/games/game-1/insults",
        headers={"Authorization": "Bearer token"},
        json={"text": "ты вонючий болотный тапок"},
    )

    assert response.status_code == 200
    payload = response.get_json()
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
