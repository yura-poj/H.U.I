from datetime import UTC, datetime

import pytest

from app.serializers import serialize_game, serialize_level


def _seed_levels():
    pytest.importorskip("psycopg")
    from app.db import SEED_LEVELS

    return SEED_LEVELS


def test_seed_levels_define_ten_active_progression_levels():
    seed_levels = _seed_levels()
    hp_by_level = [20 * 2 ** (level_number - 1) for level_number in range(1, 11)]

    assert len(seed_levels) == 10

    for level_number, level in enumerate(seed_levels, start=1):
        assert level["id"] == f"level_{level_number}"
        assert level["order_index"] == level_number
        assert level["min_words_per_insult"] == level_number
        assert level["monster_hp"] == hp_by_level[level_number - 1]
        assert level["monster_icon"] == f"{level_number}.png"
        assert level["active"] is True


def test_serialize_level_returns_icon_url_and_icon_file():
    serialized = serialize_level(
        {
            "id": "level_3",
            "order_index": 3,
            "title": "Level 3",
            "description": "Requires at least 3 word(s) per insult.",
            "monster_name": "Monster 3",
            "monster_icon": "3.png",
            "monster_hp": 80,
            "min_words_per_insult": 3,
        }
    )

    assert serialized["monster"]["icon"] == "/3.png"
    assert serialized["monster"]["icon_file"] == "3.png"


def test_serialize_game_returns_icon_url_and_icon_file():
    serialized = serialize_game(
        {
            "id": "game-1",
            "level_id": "level_4",
            "status": "active",
            "monster_name": "Monster 4",
            "monster_icon": "4.png",
            "monster_hp": 160,
            "monster_max_hp": 160,
            "min_words_per_insult": 4,
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
        }
    )

    assert serialized["monster"]["icon"] == "/4.png"
    assert serialized["monster"]["icon_file"] == "4.png"


def test_serialize_level_preserves_existing_url_icons():
    serialized = serialize_level(
        {
            "id": "swamp_troll",
            "order_index": 1001,
            "title": "Swamp Troll",
            "description": "Legacy level.",
            "monster_name": "Slopjaw",
            "monster_icon": "/image.webp",
            "monster_hp": 100,
            "min_words_per_insult": 3,
        }
    )

    assert serialized["monster"]["icon"] == "/image.webp"
    assert serialized["monster"]["icon_file"] == "/image.webp"


def test_levels_endpoint_returns_ten_seeded_levels(monkeypatch):
    flask = pytest.importorskip("flask")
    import app.routes.levels as levels_module
    from app.routes.levels import levels_bp

    seed_levels = _seed_levels()
    app = flask.Flask(__name__)
    app.register_blueprint(levels_bp, url_prefix="/api")
    monkeypatch.setattr(levels_module, "list_levels", lambda: seed_levels)

    response = app.test_client().get("/api/levels")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["levels"]) == 10

    for level_number, level in enumerate(payload["levels"], start=1):
        assert level["order"] == level_number
        assert level["rules"]["min_words_per_insult"] == level_number
        assert level["rules"]["hp"] == 20 * 2 ** (level_number - 1)
        assert level["monster"]["icon_file"] == f"{level_number}.png"
        assert level["monster"]["icon"] == f"/{level_number}.png"
