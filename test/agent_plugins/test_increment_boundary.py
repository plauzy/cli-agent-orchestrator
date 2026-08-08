"""Guards for the Increment 1 boundary and the event-plugin separation (D7).

_Requirements: 11.3, 11.4, 11.5, 21.x_

design.md states the observable test of the increment boundary plainly: *"the
Increment 1 test suite contains no test that launches a plugin subprocess"*, and
no Increment 1 code path expands ``${PLUGIN_ROOT}``/``${PLUGIN_DATA}`` or
validates against ``mcp.schema.json``. Those are checkable properties of the
source tree, so they are checked here rather than left to reviewer vigilance —
this file is what should fail if Increment 2 work leaks backwards.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "src" / "cli_agent_orchestrator" / "agent_plugins"
TEST_DIR = Path(__file__).resolve().parent

# The single module permitted to do MCP mapping, once Increment 2 begins.
INCREMENT_2_MODULE = "mcp_mapping.py"


def _increment_1_sources() -> List[Path]:
    """Every agent_plugins source module that belongs to Increment 1."""
    return sorted(path for path in PACKAGE_DIR.glob("*.py") if path.name != INCREMENT_2_MODULE)


def _test_modules() -> List[Path]:
    return sorted(TEST_DIR.glob("test_*.py"))


def _docstring_nodes(tree: ast.AST) -> set:
    """Identify every docstring Constant node, by object id.

    Docstrings must be excluded from the placeholder scan: these modules
    legitimately *discuss* ``${PLUGIN_ROOT}`` in prose while stating that they
    never expand it. An implementation, by contrast, needs the placeholder as a
    live string literal.
    """
    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstrings.add(id(body[0].value))
    return docstrings


def _live_string_literals(path: Path) -> List[str]:
    """Every string literal in ``path`` that is not a docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


class TestNoPlaceholderExpansion:
    """_Requirements: 11.3 — no ${PLUGIN_ROOT}/${PLUGIN_DATA} expansion._"""

    @pytest.mark.parametrize("source", _increment_1_sources(), ids=lambda path: path.name)
    def test_module_does_not_expand_plugin_placeholders(self, source: Path) -> None:
        """No live string literal carries the placeholder syntax.

        Docstrings are excluded deliberately: these modules describe the
        boundary in prose. An expansion implementation would need the
        placeholder as a real literal, which is what this catches.
        """
        for literal in _live_string_literals(source):
            assert (
                "${PLUGIN_ROOT}" not in literal
            ), f"{source.name} has a live ${{PLUGIN_ROOT}} literal"
            assert (
                "${PLUGIN_DATA}" not in literal
            ), f"{source.name} has a live ${{PLUGIN_DATA}} literal"

    def test_increment_2_module_does_not_exist_yet(self) -> None:
        assert not (PACKAGE_DIR / INCREMENT_2_MODULE).exists(), (
            "mcp_mapping.py is Increment 2 only and must not be present while "
            "Increment 1 is the delivered scope"
        )


class TestNoMcpSchemaValidation:
    """_Requirements: 11.3 — mcp.schema.json is committed but never validated._"""

    def test_mcp_schema_is_vendored_but_unrecognized(self) -> None:
        from cli_agent_orchestrator.agent_plugins import schema_registry

        # Committed...
        vendored = (
            REPO_ROOT
            / "src"
            / "cli_agent_orchestrator"
            / "schemas"
            / "agent_plugins"
            / schema_registry.SCHEMA_VERSION
            / "mcp.schema.json"
        )
        assert vendored.is_file()

        # ...but unreachable through the validation path.
        assert schema_registry.MCP_SCHEMA_ID not in schema_registry.RECOGNIZED_PLUGIN_SCHEMA_IDS

    @pytest.mark.parametrize("source", _increment_1_sources(), ids=lambda path: path.name)
    def test_no_module_loads_the_mcp_schema(self, source: Path) -> None:
        text = source.read_text(encoding="utf-8")

        # Referring to the constant name in a docstring is fine; calling
        # load_schema on the MCP filename is not.
        assert "load_schema(MCP_SCHEMA" not in text
        assert "load_schema(schema_registry.MCP_SCHEMA" not in text

    def test_the_validator_never_parses_mcp_json(self, tmp_path: Path) -> None:
        """A broken mcp.json must not produce a parse error in Increment 1."""
        from cli_agent_orchestrator.agent_plugins.validation import validate_plugin

        from .conftest import make_plugin

        root = make_plugin(tmp_path / "p", "example")
        (root / "mcp.json").write_text("{ definitely not json", encoding="utf-8")

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.mcp_present is True
        assert report.mcp_servers == ()
        assert [f.code for f in report.findings] == ["mcp.unsupported"]


class TestNoPluginSubprocessLaunch:
    """_Requirements: 11.4 — no test launches a plugin subprocess._"""

    @pytest.mark.parametrize("source", _test_modules(), ids=lambda path: path.name)
    def test_no_test_module_launches_a_plugin_subprocess(self, source: Path) -> None:
        """Only the resolver may spawn a process, and only ``git``.

        Walked as an AST rather than grepped so a mention inside a docstring
        cannot trip the check and a real call cannot hide from it.
        """
        tree = ast.parse(source.read_text(encoding="utf-8"))

        spawn_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            name = None
            if isinstance(target, ast.Attribute):
                name = target.attr
            elif isinstance(target, ast.Name):
                name = target.id
            if name in {"Popen", "run", "call", "check_call", "check_output", "system"}:
                spawn_calls.append(name)

        if source.name == "test_resolver.py":
            # The resolver legitimately runs git; its tests build fixture repos.
            return
        if source.name == "test_increment_boundary.py":
            return

        assert spawn_calls == [], (
            f"{source.name} appears to spawn a subprocess ({spawn_calls}); "
            f"Increment 1 must launch no plugin subprocess"
        )

    def test_installing_a_path_source_spawns_nothing(self, tmp_path: Path) -> None:
        import subprocess

        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

        from .conftest import make_plugin

        source = make_plugin(tmp_path / "src", "example", skills=("alpha",))
        store = InstalledPluginStore(plugins_dir=tmp_path / "plugins", data_dir=tmp_path / "data")
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        launched: List[object] = []
        real_popen = subprocess.Popen

        class _Recorder(real_popen):  # type: ignore[misc,valid-type]
            def __init__(self, args, *rest, **kwargs):
                launched.append(args)
                super().__init__(args, *rest, **kwargs)

        subprocess.Popen = _Recorder  # type: ignore[misc]
        try:
            outcome = installer.install(
                PluginSource(kind="path", location=str(source)),
                store=store,
                skills_dir=skills_dir,
                refresh_agents=False,
            )
        finally:
            subprocess.Popen = real_popen  # type: ignore[misc]

        assert outcome.installed is True
        assert launched == []


class TestEventPluginSurfaceUnchanged:
    """D7 regression guard: the event-plugin surface is untouched.

    ``cli_agent_orchestrator.plugins`` (event plugins, ``cao.plugins`` entry
    points) and ``cli_agent_orchestrator.agent_plugins`` (this feature) are
    unrelated. The names are confusingly close, which is exactly why the
    separation is asserted rather than assumed.
    """

    def test_event_plugin_registry_still_imports(self) -> None:
        from cli_agent_orchestrator.plugins import PluginRegistry

        assert PluginRegistry is not None

    def test_no_import_edge_from_agent_plugins_to_event_plugins(self) -> None:
        for source in _increment_1_sources():
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(
                        "cli_agent_orchestrator.plugins"
                    ), f"{source.name} imports the event-plugin package"
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith(
                            "cli_agent_orchestrator.plugins"
                        ), f"{source.name} imports the event-plugin package"

    def test_no_agent_plugins_symbol_shadows_an_event_plugin_symbol(self) -> None:
        import cli_agent_orchestrator.agent_plugins as agent_plugins
        import cli_agent_orchestrator.plugins as event_plugins

        agent_public = {name for name in dir(agent_plugins) if not name.startswith("_")}
        event_public = {name for name in dir(event_plugins) if not name.startswith("_")}

        assert agent_public & event_public == set()

    def test_the_two_packages_are_distinct_modules(self) -> None:
        import cli_agent_orchestrator.agent_plugins as agent_plugins
        import cli_agent_orchestrator.plugins as event_plugins

        assert Path(agent_plugins.__file__).parent != Path(event_plugins.__file__).parent


class TestOperatorPackageShipsNoMcpJson:
    """_Requirements: 11.5 — CAO's own package carries no mcp.json yet._"""

    def test_no_mcp_json_in_the_operator_package(self) -> None:
        package = REPO_ROOT / "agent-plugin" / "cao"
        if not package.is_dir():
            pytest.skip("the CAO operator package is built in W9")

        assert not (package / "mcp.json").exists()
