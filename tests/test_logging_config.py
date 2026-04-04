import logging

import pytest
from pythonjsonlogger.json import JsonFormatter

from src.logging_config import setup_logging


@pytest.fixture(autouse=True)
def _clean_logging():
    """Reset root logger state between tests."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.level = original_level


class TestSetupLogging:
    def test_default_log_level_is_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        setup_logging()
        assert logging.getLogger().level == logging.INFO

    def test_log_level_override(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        setup_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_log_level_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        setup_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_text_format_is_default(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        setup_logging()
        handler = logging.getLogger().handlers[0]
        assert not isinstance(handler.formatter, JsonFormatter)

    def test_json_format_when_requested(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        setup_logging()
        handler = logging.getLogger().handlers[0]
        assert isinstance(handler.formatter, JsonFormatter)

    @pytest.mark.parametrize("logger_name", ["httpx", "httpcore"])
    def test_http_loggers_at_least_info(self, monkeypatch, logger_name):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        setup_logging()
        assert logging.getLogger(logger_name).level >= logging.INFO
