"""Each pytest-xdist worker runs under its own fake HOME (see test/conftest.py)."""

import os
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not os.environ.get("PYTEST_XDIST_WORKER"), reason="only meaningful under pytest-xdist"
)
def test_each_worker_has_its_own_fake_home() -> None:
    home = Path(os.environ["HOME"])
    assert home.name == os.environ["PYTEST_XDIST_WORKER"]
    assert home.parent.name.startswith("cao-test-home-")
    from cli_agent_orchestrator.constants import CAO_HOME_DIR

    assert Path(CAO_HOME_DIR).resolve().is_relative_to(home.resolve())
