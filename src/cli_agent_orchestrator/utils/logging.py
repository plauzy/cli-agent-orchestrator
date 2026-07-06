import logging
import re
import sys
from datetime import datetime

from cli_agent_orchestrator.constants import LOG_DIR
from cli_agent_orchestrator.services.config_service import ConfigService

# Query-string credentials that must never be written to access logs. The
# AG-UI SSE stream accepts a bearer JWT via ``?access_token=`` because browser
# ``EventSource`` cannot set an Authorization header; the full request line
# (path + query) otherwise lands verbatim in uvicorn's access log, proxy logs,
# and Referer headers, where a captured token is replayable until it expires.
# We scrub the value while keeping the log line otherwise intact so access
# logging stays useful. (A short-lived single-use ``?ticket=`` handshake is a
# planned follow-up; it is redacted here too, pre-emptively.)
_SENSITIVE_QUERY_PARAMS = ("access_token", "ticket")
_QUERY_TOKEN_RE = re.compile(
    r"(" + "|".join(re.escape(p) for p in _SENSITIVE_QUERY_PARAMS) + r")=[^&\s\"']+"
)


class RedactQueryTokenFilter(logging.Filter):
    """Logging filter that masks sensitive query-string params in log records.

    uvicorn's access logger formats the request line via ``record.args``; we
    rewrite any string arg in place so ``?access_token=<jwt>`` becomes
    ``?access_token=REDACTED`` before the record is emitted. Returns True so the
    record is always logged (redacted), never dropped.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(
                _QUERY_TOKEN_RE.sub(r"\1=REDACTED", a) if isinstance(a, str) else a for a in args
            )
        # Defensive: some handlers pre-render the message onto ``msg``.
        if isinstance(record.msg, str) and "=" in record.msg:
            record.msg = _QUERY_TOKEN_RE.sub(r"\1=REDACTED", record.msg)
        return True


def install_access_log_redaction() -> None:
    """Attach :class:`RedactQueryTokenFilter` to uvicorn's access logger.

    Idempotent — safe to call more than once (won't stack duplicate filters).
    Call before ``uvicorn.run`` so the filter is present for every access line.
    """
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactQueryTokenFilter) for f in access_logger.filters):
        access_logger.addFilter(RedactQueryTokenFilter())


def setup_logging() -> None:
    """Setup logging configuration."""
    log_level = str(ConfigService.get("logging.level", default="INFO")).upper()

    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"cao_{timestamp}.log"

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Stream handler: WARNING+ always goes to stderr so operationally-relevant
    # events surface on the console (and in a subprocess's captured stdout/stderr,
    # which the e2e harness asserts on) rather than being buried in the log file.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter(fmt))

    logging.basicConfig(
        level=log_level,
        format=fmt,
        handlers=[logging.FileHandler(log_file), stderr_handler],
    )

    print(f"Server logs: {log_file}")
    print("For debug logs: export CAO_LOG_LEVEL=DEBUG && cao-server")
    logging.info(f"Logging to: {log_file}")
