import logging
import sys
from app.config.settings import config
import os


def setup_logging():
    cfg = config[os.getenv("FLASK_ENV", "default")]

    log_level = logging.DEBUG if cfg.DEBUG else logging.INFO

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    return root_logger