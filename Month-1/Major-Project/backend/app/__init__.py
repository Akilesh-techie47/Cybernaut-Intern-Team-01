from flask import Flask, request
from flask_cors import CORS
from app.config.settings import config
from app.utils.logging import setup_logging
from app.database.connection import get_db, close_db
import os
import logging

logger = logging.getLogger(__name__)


def create_app(config_name: str = None) -> Flask:
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "default")

    app = Flask(__name__)
    cfg = config[config_name]
    app.config.from_object(cfg)

    CORS(app, origins=[cfg.FRONTEND_URL], supports_credentials=True)

    setup_logging()

    @app.before_request
    def log_request():
        logger.info(f"{request.method} {request.path}")

    from app.routes.health import health_bp
    from app.routes.products import products_bp
    from app.routes.scraping import scraping_bp
    from app.routes.stats import stats_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(products_bp, url_prefix="/api")
    app.register_blueprint(scraping_bp, url_prefix="/api")
    app.register_blueprint(stats_bp, url_prefix="/api")

    @app.errorhandler(404)
    def not_found(e):
        from app.utils.responses import not_found_response
        return not_found_response("Endpoint")

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal error: {e}")
        from app.utils.responses import internal_error_response
        return internal_error_response()

    logger.info(f"Flask app created in {config_name} mode")
    return app