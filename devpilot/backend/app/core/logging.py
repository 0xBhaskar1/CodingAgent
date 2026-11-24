import logging
import sys
from app.core.config import Settings


def setup_logging(settings: Settings) -> None:
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    numeric_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
