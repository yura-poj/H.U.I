def create_app():
    from flask import Flask
    from flask_cors import CORS

    from app.config import Config
    from app.db import init_db
    from app.routes.auth import auth_bp
    from app.routes.games import games_bp
    from app.routes.health import health_bp
    from app.routes.insults import insults_bp
    from app.routes.levels import levels_bp
    from app.routes.leaderboard import leaderboard_bp
    from app.security import configure_rate_limiting

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS)

    init_db()
    configure_rate_limiting(app)

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(games_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(insults_bp, url_prefix="/api")
    app.register_blueprint(leaderboard_bp, url_prefix="/api")
    app.register_blueprint(levels_bp, url_prefix="/api")

    return app
