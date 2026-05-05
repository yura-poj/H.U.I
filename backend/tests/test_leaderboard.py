import pytest


def test_leaderboard_top_forces_ten_item_page(monkeypatch):
    flask = pytest.importorskip("flask")
    import app.auth as auth_module
    import app.routes.leaderboard as leaderboard_module
    from app.routes.leaderboard import leaderboard_bp

    app = flask.Flask(__name__)
    app.register_blueprint(leaderboard_bp, url_prefix="/api")
    captured = {}

    monkeypatch.setattr(
        auth_module,
        "find_user_by_token",
        lambda token: {"id": "user-1", "username": "player", "current_level_id": "level_1"},
    )

    def fake_list_leaderboard(**kwargs):
        captured.update(kwargs)
        return [], {
            "rank": 12,
            "username": "player",
            "total_damage": 5,
            "insults_count": 1,
            "current_level_id": "level_1",
        }

    monkeypatch.setattr(leaderboard_module, "list_leaderboard", fake_list_leaderboard)

    response = app.test_client().get(
        "/api/leaderboard?section=top&page_size=100",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert captured == {
        "current_user_id": "user-1",
        "section": "top",
        "page": 1,
        "page_size": 10,
    }
    assert response.get_json()["current_user_rank"]["rank"] == 12


def test_leaderboard_all_uses_requested_pagination(monkeypatch):
    flask = pytest.importorskip("flask")
    import app.auth as auth_module
    import app.routes.leaderboard as leaderboard_module
    from app.routes.leaderboard import leaderboard_bp

    app = flask.Flask(__name__)
    app.register_blueprint(leaderboard_bp, url_prefix="/api")
    captured = {}

    monkeypatch.setattr(
        auth_module,
        "find_user_by_token",
        lambda token: {"id": "user-1", "username": "player", "current_level_id": "level_1"},
    )

    def fake_list_leaderboard(**kwargs):
        captured.update(kwargs)
        return [
            {
                "rank": 1,
                "username": "player",
                "total_damage": 5,
                "insults_count": 1,
                "current_level_id": "level_1",
            }
        ], None

    monkeypatch.setattr(leaderboard_module, "list_leaderboard", fake_list_leaderboard)

    response = app.test_client().get(
        "/api/leaderboard?section=all&page=2&page_size=25",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert captured == {
        "current_user_id": "user-1",
        "section": "all",
        "page": 2,
        "page_size": 25,
    }
    assert response.get_json()["leaders"][0]["rank"] == 1


def test_leaderboard_rejects_old_others_section(monkeypatch):
    flask = pytest.importorskip("flask")
    import app.auth as auth_module
    from app.routes.leaderboard import leaderboard_bp

    app = flask.Flask(__name__)
    app.register_blueprint(leaderboard_bp, url_prefix="/api")

    monkeypatch.setattr(
        auth_module,
        "find_user_by_token",
        lambda token: {"id": "user-1", "username": "player", "current_level_id": "level_1"},
    )

    response = app.test_client().get(
        "/api/leaderboard?section=others",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_leaderboard_section"
