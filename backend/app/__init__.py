def create_app():
    from flask import Flask
    from flask_cors import CORS

    from app.db import init_db
    from app.routes.auth import auth_bp
    from app.routes.games import games_bp
    from app.routes.health import health_bp
    from app.routes.levels import levels_bp

    app = Flask(__name__)
    CORS(app)

    init_db()

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(games_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(levels_bp, url_prefix="/api")

    return app
