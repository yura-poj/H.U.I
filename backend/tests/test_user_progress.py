import pytest


def test_start_game_uses_saved_user_monster_hp(monkeypatch):
    flask = pytest.importorskip("flask")
    import app.auth as auth_module
    import app.routes.games as games_module
    from app.routes.games import games_bp

    app = flask.Flask(__name__)
    app.register_blueprint(games_bp, url_prefix="/api")
    captured = {}

    level = {
        "id": "level_1",
        "monster_hp": 20,
    }
    full_game = {
        "id": "game-1",
        "level_id": "level_1",
        "status": "active",
        "monster_name": "Monster 1",
        "monster_icon": "1.png",
        "monster_hp": 7,
        "monster_max_hp": 20,
        "min_words_per_insult": 1,
    }

    monkeypatch.setattr(
        auth_module,
        "find_user_by_token",
        lambda token: {
            "id": "user-1",
            "username": "player",
            "current_level_id": "level_1",
            "current_monster_hp": 7,
        },
    )
    monkeypatch.setattr(games_module, "get_level", lambda level_id: level)

    def fake_create_game(**kwargs):
        captured.update(kwargs)
        return {"id": "game-1"}

    monkeypatch.setattr(games_module, "create_game", fake_create_game)
    monkeypatch.setattr(games_module, "get_game_for_user", lambda game_id, user_id: full_game)

    response = app.test_client().post(
        "/api/games",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 201
    assert captured["monster_hp"] == 7
    assert response.get_json()["game"]["monster"]["hp"] == 7


def test_submit_insult_returns_next_level_saved_monster_hp(monkeypatch):
    flask = pytest.importorskip("flask")
    import app.auth as auth_module
    import app.routes.games as games_module
    from app.routes.games import games_bp

    app = flask.Flask(__name__)
    app.register_blueprint(games_bp, url_prefix="/api")

    active_game = {
        "id": "game-1",
        "user_id": "user-1",
        "level_id": "level_1",
        "monster_hp": 3,
        "status": "active",
        "monster_name": "Monster 1",
        "monster_icon": "1.png",
        "monster_max_hp": 20,
        "min_words_per_insult": 1,
    }
    won_game = {
        **active_game,
        "monster_hp": 0,
        "status": "won",
    }
    games = iter([active_game, won_game])

    monkeypatch.setattr(
        auth_module,
        "find_user_by_token",
        lambda token: {
            "id": "user-1",
            "username": "player",
            "current_level_id": "level_1",
            "current_monster_hp": 3,
        },
    )
    monkeypatch.setattr(games_module, "get_game_for_user", lambda game_id, user_id: next(games))
    monkeypatch.setattr(games_module, "has_used_insult", lambda user_id, normalized_text: False)
    monkeypatch.setattr(
        games_module,
        "score_insult",
        lambda text: {
            "damage": 5,
            "source": "model",
            "toxic": False,
            "toxicity_score": 0.1,
            "label": "normal",
            "signals": {},
        },
    )
    monkeypatch.setattr(games_module, "apply_insult_damage", lambda **kwargs: {"id": "game-1"})
    monkeypatch.setattr(
        games_module,
        "advance_user_level_if_possible",
        lambda user_id, current_level_id: {
            "id": "user-1",
            "username": "player",
            "current_level_id": "level_2",
            "current_monster_hp": 40,
        },
    )

    response = app.test_client().post(
        "/api/games/game-1/insults",
        headers={"Authorization": "Bearer token"},
        json={"text": "weak"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["advanced_to_level_id"] == "level_2"
    assert payload["advanced_to_monster_hp"] == 40
