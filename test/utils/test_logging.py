"""Tests for logging utility."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_agent_orchestrator.utils.logging import setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    def test_setup_logging_default_level(self, mock_basic_config, mock_log_dir):
        """Test setup_logging with default INFO level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch.dict("os.environ", {}, clear=True):
                with patch("builtins.print"):
                    setup_logging()

            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == "INFO"

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    def test_setup_logging_debug_level(self, mock_basic_config, mock_log_dir):
        """Test setup_logging with DEBUG level from env var."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch.dict("os.environ", {"CAO_LOG_LEVEL": "DEBUG"}):
                with patch("builtins.print"):
                    setup_logging()

            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == "DEBUG"

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    def test_setup_logging_warning_level(self, mock_basic_config, mock_log_dir):
        """Test setup_logging with WARNING level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch.dict("os.environ", {"CAO_LOG_LEVEL": "warning"}):
                with patch("builtins.print"):
                    setup_logging()

            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == "WARNING"

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    def test_setup_logging_creates_log_directory(self, mock_basic_config, mock_log_dir):
        """Test setup_logging creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch("builtins.print"):
                setup_logging()

            mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    def test_setup_logging_prints_info(self, mock_basic_config, mock_log_dir):
        """Test setup_logging prints log file location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch("builtins.print") as mock_print:
                setup_logging()

            # Should print log file location
            assert mock_print.call_count == 2
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("Server logs" in str(call) for call in calls)

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    @patch("cli_agent_orchestrator.utils.logging.logging.info")
    def test_setup_logging_logs_info(self, mock_log_info, mock_basic_config, mock_log_dir):
        """Test setup_logging logs info message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch("builtins.print"):
                setup_logging()

            mock_log_info.assert_called_once()
            assert "Logging to" in str(mock_log_info.call_args)

    @patch("cli_agent_orchestrator.utils.logging.LOG_DIR")
    @patch("cli_agent_orchestrator.utils.logging.logging.basicConfig")
    def test_setup_logging_format(self, mock_basic_config, mock_log_dir):
        """Test setup_logging uses correct log format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_log_dir.__truediv__ = lambda self, x: Path(tmpdir) / x
            mock_log_dir.mkdir = MagicMock()

            with patch("builtins.print"):
                setup_logging()

            call_kwargs = mock_basic_config.call_args[1]
            assert "format" in call_kwargs
            assert "%(asctime)s" in call_kwargs["format"]
            assert "%(name)s" in call_kwargs["format"]
            assert "%(levelname)s" in call_kwargs["format"]


class TestRedactQueryTokenFilter:
    """Tests for the access-log query-token redaction filter."""

    def _record(self, msg, args):
        return logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=args,
            exc_info=None,
        )

    def test_redacts_access_token_in_args(self):
        from cli_agent_orchestrator.utils.logging import RedactQueryTokenFilter

        f = RedactQueryTokenFilter()
        # Mirrors uvicorn's access record: request line (with query) is an arg.
        record = self._record(
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1:5555", "GET", "/agui/v1/stream?access_token=eyJhbGciSECRET", "1.1", 200),
        )
        assert f.filter(record) is True
        rendered = record.getMessage()
        assert "eyJhbGciSECRET" not in rendered
        assert "access_token=REDACTED" in rendered
        # The rest of the request line is preserved.
        assert "/agui/v1/stream" in rendered and "GET" in rendered

    def test_redacts_ticket_param(self):
        from cli_agent_orchestrator.utils.logging import RedactQueryTokenFilter

        f = RedactQueryTokenFilter()
        record = self._record("%s", ("/agui/v1/stream?ticket=abc123DEF&x=1",))
        f.filter(record)
        rendered = record.getMessage()
        assert "abc123DEF" not in rendered
        assert "ticket=REDACTED" in rendered
        assert "x=1" in rendered  # non-sensitive params untouched

    def test_leaves_plain_lines_untouched(self):
        from cli_agent_orchestrator.utils.logging import RedactQueryTokenFilter

        f = RedactQueryTokenFilter()
        record = self._record(
            '%s - "%s %s HTTP/%s" %d', ("127.0.0.1", "GET", "/health", "1.1", 200)
        )
        f.filter(record)
        assert record.getMessage().endswith('"GET /health HTTP/1.1" 200')

    def test_install_is_idempotent(self):
        from cli_agent_orchestrator.utils.logging import (
            RedactQueryTokenFilter,
            install_access_log_redaction,
        )

        access_logger = logging.getLogger("uvicorn.access")
        before = [f for f in access_logger.filters if isinstance(f, RedactQueryTokenFilter)]
        for existing in before:
            access_logger.removeFilter(existing)
        install_access_log_redaction()
        install_access_log_redaction()
        matches = [f for f in access_logger.filters if isinstance(f, RedactQueryTokenFilter)]
        assert len(matches) == 1
