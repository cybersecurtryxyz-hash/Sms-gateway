import logging
import os

from flask import Flask

from .config import Config
from .db import init_db
from .extensions import limiter
from .routes import pages_bp, admin_bp, coworker_bp, device_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(
        level=logging.INFO if not Config.DEBUG else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Fail fast rather than silently booting with a guessable admin
    # password / device token / signing key in production.
    Config.validate()

    if Config.DEBUG:
        logger.warning(
            "Running in DEVELOPMENT mode with randomly generated, "
            "non-persistent secrets. Never use FLASK_ENV=development in "
            "production."
        )

    limiter.init_app(app)

    with app.app_context():
        init_db()

    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(coworker_bp)
    app.register_blueprint(device_bp)

    @app.after_request
    def set_security_headers(response):
        # Defense-in-depth: even though templates now escape all
        # user-controlled data, these headers reduce the blast radius of
        # any future XSS/clickjacking/mime-sniffing issue.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data:; "
            # Tailwind's CDN build (used by admin.html/app.html) generates
            # CSS via a <script> tag - it must be explicitly allowlisted or
            # the whole UI renders unstyled (this bit us once already).
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com;",
        )
        return response

    return app
