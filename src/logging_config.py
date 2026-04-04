import logging.config
import os


def setup_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "text").lower()

    if log_format == "json":
        formatter_config = {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    else:
        formatter_config = {
            "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
        }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": formatter_config,
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "default",
                },
            },
            "loggers": {
                "src": {
                    "level": log_level,
                },
                "discord": {
                    "level": "INFO",
                },
                "httpx": {
                    "level": "WARNING",
                },
                "http": {
                    "level": "INFO",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
    )
