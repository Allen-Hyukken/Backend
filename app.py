"""
app.py — Flask application factory

host="0.0.0.0" means the server listens on ALL network interfaces,
so your phone can reach it over Wi-Fi at http://<PC-LAN-IP>:5000
"""

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError

from config import Config
from extensions import db, cors


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Extensions ─────────────────────────────────────────────────────────
    db.init_app(app)
    JWTManager(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # ── Blueprints ──────────────────────────────────────────────────────────
    from routes.auth       import auth_bp
    from routes.classrooms import classroom_bp
    from routes.quizzes    import quiz_bp
    from routes.attempts   import attempt_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(attempt_bp)

    # ── Health-check endpoint (no auth required) ────────────────────────────
    # Flutter's ConnectionCheckScreen hits this to verify:
    #   1. Flask is reachable over Wi-Fi
    #   2. MySQL connection is working
    @app.get("/api/ping")
    def ping():
        db_status = "ok"
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception as e:
            db_status = f"error: {e}"
        return jsonify({"status": "ok", "db": db_status}), 200

    # ── Global error handlers ───────────────────────────────────────────────
    @app.errorhandler(RuntimeError)
    def handle_runtime(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(ValueError)
    def handle_value_error(e):
        return jsonify({"error": str(e)}), 422

    @app.errorhandler(PermissionError)
    def handle_permission(e):
        return jsonify({"error": str(e)}), 401

    @app.errorhandler(LookupError)
    def handle_lookup(e):
        return jsonify({"error": str(e)}), 409

    @app.errorhandler(NoAuthorizationError)
    @app.errorhandler(InvalidHeaderError)
    def handle_jwt_error(e):
        return jsonify({"error": "Missing or invalid authorization token"}), 401

    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify({"error": "Access denied"}), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(413)
    def handle_too_large(e):
        return jsonify({"error": "File too large (max 16 MB)"}), 413

    @app.errorhandler(500)
    def handle_server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    create_app().run(debug=True, host="0.0.0.0", port=5000)