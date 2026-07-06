import logging

from flask import Flask

from .config import Config
from .db import init_db
from .routes import pages_bp, admin_bp, coworker_bp, device_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(
        level=logging.INFO if not Config.DEBUG else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    insecure = Config.insecure_defaults_in_use()
    if insecure:
        msg = (
            "The following secrets are still on their insecure built-in defaults: "
            f"{', '.join(insecure)}. Set real values via environment variables. "
            "(Local dev override: set ALLOW_INSECURE_DEFAULTS=true if you really "
            "mean to run this way.)"
        )
        if Config.running_on_hosted_platform() and not Config.ALLOW_INSECURE_DEFAULTS:
            # Refuse to boot a real deployment with guessable secrets - this is
            # what let anyone log into /admin with "admin123" or forge the
            # device Bearer token before.
            raise RuntimeError("Refusing to start: " + msg)
        logger.warning(msg)

    with app.app_context():
        init_db()

    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(coworker_bp)
    app.register_blueprint(device_bp)

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    return app
