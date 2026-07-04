"""Package marker for vendored Zellij assets.

Hatch's ``[tool.hatch.build.targets.wheel.force-include]`` table mirrors
``zellij/layouts/cao.kdl`` and ``zellij/zellaude.wasm`` from the repo
root into this package directory at wheel-build time, so
``importlib.resources.files("cli_agent_orchestrator.zellij_assets")``
resolves them in pip-installed environments.

For editable installs the assets remain at the repo-root ``zellij/``
directory; the ``cao zellij install`` command falls back to that path
when a resource is missing. See ``cli/commands/zellij.py``.
"""
