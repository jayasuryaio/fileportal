"""FilePortal application factory."""
import os

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

from . import auth, db, files  # noqa: E402  (after load_dotenv so Config sees .env)
from .config import Config  # noqa: E402
from .security import csrf_token, load_user, protect_csrf  # noqa: E402


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    if app.config["SECRET_KEY"] == "dev-only-insecure-key" and not app.debug \
            and os.getenv("FLASK_ENV") != "development" and not app.config.get("TESTING"):
        app.logger.warning("SECRET_KEY is not set - sessions are insecure!")
    if not app.config.get("SKIP_DB_INIT"):
        db.init_schema(app.config["DB"])

    app.teardown_appcontext(db.close_db)
    app.before_request(load_user)
    app.before_request(protect_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.register_blueprint(auth.bp)
    app.register_blueprint(files.bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    def _error(code, title, message):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return _error(400, "Bad request", getattr(e, "description", "Invalid request."))

    @app.errorhandler(404)
    def not_found(_e):
        return _error(404, "Not found", "The page or file you asked for doesn't exist.")

    @app.errorhandler(413)
    def too_large(_e):
        return _error(413, "File too large",
                      f"Uploads are limited to {app.config['MAX_UPLOAD_MB']} MB.")

    @app.errorhandler(500)
    def server_error(_e):
        return _error(500, "Something went wrong", "Please try again in a moment.")

    return app
