import flask
import pytest

import app.repositories as repositories
import app.routes.auth as auth_routes
from app.security import FixedWindowRateLimiter, get_client_ip


def _auth_app():
    app = flask.Flask(__name__)
    app.register_blueprint(auth_routes.auth_bp, url_prefix="/api")
    return app


def test_register_passes_client_ip_to_user_creation(monkeypatch):
    captured = {}

    def fake_create_user(username, password_hash, registration_ip):
        captured["username"] = username
        captured["password_hash"] = password_hash
        captured["registration_ip"] = registration_ip
        return {
            "id": "user-1",
            "username": username,
            "current_level_id": "level_1",
            "current_monster_hp": 20,
            "created_at": None,
        }

    monkeypatch.setattr(auth_routes, "create_user", fake_create_user)
    monkeypatch.setattr(auth_routes, "create_auth_token", lambda user_id: "token-1")
    monkeypatch.setattr(auth_routes, "generate_password_hash", lambda password: f"hash:{password}")

    client = _auth_app().test_client()
    response = client.post(
        "/api/users/register",
        json={"username": "player1", "password": "secret1"},
        environ_overrides={"REMOTE_ADDR": "203.0.113.10"},
    )

    assert response.status_code == 201
    assert captured == {
        "username": "player1",
        "password_hash": "hash:secret1",
        "registration_ip": "203.0.113.10",
    }


def test_register_returns_429_when_ip_registration_limit_is_exceeded(monkeypatch):
    def fake_create_user(username, password_hash, registration_ip):
        raise auth_routes.RegistrationIpLimitExceeded(registration_ip)

    monkeypatch.setattr(auth_routes, "create_user", fake_create_user)

    client = _auth_app().test_client()
    response = client.post(
        "/api/users/register",
        json={"username": "player4", "password": "secret4"},
        environ_overrides={"REMOTE_ADDR": "203.0.113.10"},
    )

    assert response.status_code == 429
    assert response.get_json() == {"error": "registration_ip_limit_exceeded", "limit": 3}


def test_create_user_uses_one_day_registration_ip_window(monkeypatch):
    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query, params=None):
            if "registration_ip_limits" in query:
                captured["query"] = query
                captured["params"] = params
                self.next_fetch = {"successful_registrations": 1}
                return

            if "insert into users" in query:
                self.next_fetch = {
                    "id": "user-1",
                    "username": params[1],
                    "current_level_id": params[4],
                    "current_monster_hp": params[5],
                    "created_at": None,
                }

        def fetchone(self):
            return self.next_fetch

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(
        repositories,
        "get_first_level",
        lambda: {"id": "level_1", "monster_hp": 20},
    )
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection())
    monkeypatch.setattr(repositories.Config, "REGISTRATION_IP_LIMIT", 3)
    monkeypatch.setattr(repositories.Config, "REGISTRATION_IP_WINDOW_SECONDS", 86400)

    user = repositories.create_user("player1", "hash", "203.0.113.10")
    normalized_query = " ".join(captured["query"].split())

    assert user["username"] == "player1"
    assert captured["params"] == ("203.0.113.10", 86400, 86400, 3)
    assert "then 1" in normalized_query
    assert "updated_at <= now() - make_interval(secs => %s)" in normalized_query


def test_create_user_allows_three_successful_registrations_from_same_ip_and_blocks_fourth(monkeypatch):
    registration_count = 0
    inserted_users = []
    commits = 0
    rollbacks = 0

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query, params=None):
            nonlocal registration_count

            if "registration_ip_limits" in query:
                if registration_count >= 3:
                    self.next_fetch = None
                    return

                registration_count += 1
                self.next_fetch = {"successful_registrations": registration_count}
                return

            if "insert into users" in query:
                inserted_users.append(params[1])
                self.next_fetch = {
                    "id": f"user-{len(inserted_users)}",
                    "username": params[1],
                    "current_level_id": params[4],
                    "current_monster_hp": params[5],
                    "created_at": None,
                }

        def fetchone(self):
            return self.next_fetch

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            nonlocal commits
            commits += 1

        def rollback(self):
            nonlocal rollbacks
            rollbacks += 1

    monkeypatch.setattr(
        repositories,
        "get_first_level",
        lambda: {"id": "level_1", "monster_hp": 20},
    )
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection())

    for index in range(1, 4):
        user = repositories.create_user(f"player{index}", "hash", "203.0.113.10")
        assert user["username"] == f"player{index}"

    with pytest.raises(repositories.RegistrationIpLimitExceeded):
        repositories.create_user("player4", "hash", "203.0.113.10")

    assert inserted_users == ["player1", "player2", "player3"]
    assert commits == 3
    assert rollbacks == 1


def test_create_user_rolls_back_when_registration_ip_limit_is_exceeded(monkeypatch):
    statements = []
    rolled_back = False

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query, params=None):
            statements.append(" ".join(query.split()))
            self.next_fetch = None

        def fetchone(self):
            return self.next_fetch

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            raise AssertionError("limited registration must not commit")

        def rollback(self):
            nonlocal rolled_back
            rolled_back = True

    monkeypatch.setattr(
        repositories,
        "get_first_level",
        lambda: {"id": "level_1", "monster_hp": 20},
    )
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection())

    try:
        repositories.create_user("player4", "hash", "203.0.113.10")
    except repositories.RegistrationIpLimitExceeded:
        pass
    else:
        raise AssertionError("expected registration IP limit to be enforced")

    assert rolled_back is True
    assert len(statements) == 1
    assert "insert into registration_ip_limits" in statements[0]
    assert "insert into users" not in statements[0]


def test_get_client_ip_ignores_forwarded_for_unless_proxy_headers_are_trusted():
    app = flask.Flask(__name__)
    app.config["TRUST_PROXY_HEADERS"] = False

    with app.test_request_context(
        "/api/ping",
        headers={"X-Forwarded-For": "198.51.100.55"},
        environ_overrides={"REMOTE_ADDR": "203.0.113.20"},
    ):
        assert get_client_ip() == "203.0.113.20"


def test_get_client_ip_uses_first_forwarded_for_when_proxy_headers_are_trusted():
    app = flask.Flask(__name__)
    app.config["TRUST_PROXY_HEADERS"] = True

    with app.test_request_context(
        "/api/ping",
        headers={"X-Forwarded-For": "198.51.100.55, 10.0.0.8"},
        environ_overrides={"REMOTE_ADDR": "203.0.113.20"},
    ):
        assert get_client_ip() == "198.51.100.55"


def test_fixed_window_rate_limiter_allows_requests_after_window_expires():
    now = 100.0
    limiter = FixedWindowRateLimiter(max_requests=2, window_seconds=10, now=lambda: now)

    assert limiter.allow("203.0.113.10") == (True, 0)
    assert limiter.allow("203.0.113.10") == (True, 0)
    assert limiter.allow("203.0.113.10") == (False, 10)

    now = 110.0

    assert limiter.allow("203.0.113.10") == (True, 0)


def test_rate_limiter_blocks_repeated_api_requests_from_same_ip():
    from app.security import configure_rate_limiting

    app = flask.Flask(__name__)
    app.config.update(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_MAX_REQUESTS=2,
        RATE_LIMIT_WINDOW_SECONDS=60,
    )
    configure_rate_limiting(app)

    @app.get("/api/ping")
    def ping():
        return flask.jsonify({"ok": True})

    client = app.test_client()

    for _ in range(2):
        response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.7"})
        assert response.status_code == 200

    response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.7"})

    assert response.status_code == 429
    assert response.get_json()["error"] == "rate_limit_exceeded"


def test_rate_limiter_tracks_client_ips_independently():
    from app.security import configure_rate_limiting

    app = flask.Flask(__name__)
    app.config.update(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_MAX_REQUESTS=1,
        RATE_LIMIT_WINDOW_SECONDS=60,
    )
    configure_rate_limiting(app)

    @app.get("/api/ping")
    def ping():
        return flask.jsonify({"ok": True})

    client = app.test_client()

    first_ip_response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.7"})
    second_ip_response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.8"})
    blocked_response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.7"})

    assert first_ip_response.status_code == 200
    assert second_ip_response.status_code == 200
    assert blocked_response.status_code == 429


def test_rate_limiter_can_be_disabled_for_api_requests():
    from app.security import configure_rate_limiting

    app = flask.Flask(__name__)
    app.config.update(
        RATE_LIMIT_ENABLED=False,
        RATE_LIMIT_MAX_REQUESTS=1,
        RATE_LIMIT_WINDOW_SECONDS=60,
    )
    configure_rate_limiting(app)

    @app.get("/api/ping")
    def ping():
        return flask.jsonify({"ok": True})

    client = app.test_client()

    first_response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.7"})
    second_response = client.get("/api/ping", environ_overrides={"REMOTE_ADDR": "198.51.100.7"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
