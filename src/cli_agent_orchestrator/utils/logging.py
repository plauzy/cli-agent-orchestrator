import logging
import sys
from datetime import datetime

from cli_agent_orchestrator.constants import LOG_DIR
from cli_agent_orchestrator.services.config_service import ConfigService


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
