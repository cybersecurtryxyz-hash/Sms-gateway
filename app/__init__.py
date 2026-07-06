import logging
import os

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

    if not os.environ.get("ADMIN_PASSWORD"):
        logger.warning(
            "ADMIN_PASSWORD is not set - using an insecure default. "
            "Set it before deploying to production."
        )
    if not os.environ.get("DEVICE_TOKEN"):
        logger.warning(
            "DEVICE_TOKEN is not set - using an insecure default. "
            "Set it before deploying to production."
        )

    with app.app_context():
        init_db()

    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(coworker_bp)
    app.register_blueprint(device_bp)

    return app
