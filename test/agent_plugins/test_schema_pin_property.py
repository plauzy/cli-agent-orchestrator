"""Property 11: Schema pin integrity and offline validation.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

Two halves, both required by §5.2's prohibition on retrieving a schema while
loading a plugin:

* **Pin integrity** — the vendored bytes hash to the values recorded in
  ``PIN.json``, and the manifest agrees with the vendoring script's constants.
* **Offline validation** — with socket creation blocked outright, building a
  validator and validating a manifest still succeeds.

The vendoring script's constants are imported *from the script* rather than
duplicated here, following ``test/test_skill_packaging_parity.py``: a drift
guard that keeps its own copy of the thing it guards is guarding nothing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator

from cli_agent_orchestrator.agent_plugins import schema_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_SCRIPT = REPO_ROOT / "scripts" / "vendor_agent_plugins_schemas.py"


def _load_vendor_script() -> ModuleType:
    """Import the vendoring script by path (single source of truth)."""
    spec = importlib.util.spec_from_file_location("_vendor_agent_plugins_schemas", VENDOR_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VENDOR = _load_vendor_script()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPinIntegrity:
    """_Requirements: 4.2, 4.3 — recorded provenance and hash per file._"""

    def test_vendor_script_exists_and_is_executable_style(self) -> None:
        assert VENDOR_SCRIPT.is_file()

    def test_pin_manifest_exists(self) -> None:
        assert VENDOR.PIN_PATH.is_file(), "PIN.json is missing; run the refresh target"

    @pytest.mark.parametrize("filename", VENDOR.SCHEMA_FILES)
    def test_vendored_file_exists(self, filename: str) -> None:
        assert (VENDOR.VENDOR_DIR / filename).is_file()

    @pytest.mark.parametrize("filename", VENDOR.SCHEMA_FILES)
    def test_vendored_bytes_hash_to_recorded_value(self, filename: str) -> None:
        """The core of P11: bytes on disk == bytes the pin claims."""
        pin: Dict[str, Any] = json.loads(VENDOR.PIN_PATH.read_text(encoding="utf-8"))

        recorded = pin["files"][filename]["sha256"]
        actual = _sha256(VENDOR.VENDOR_DIR / filename)

        assert actual == recorded, f"{filename} drifted from PIN.json"

    def test_pin_records_the_scripts_commit(self) -> None:
        pin = json.loads(VENDOR.PIN_PATH.read_text(encoding="utf-8"))

        assert pin["commit"] == VENDOR.PINNED_SHA
        assert pin["ref"] == VENDOR.PINNED_REF
        assert pin["source_url"] == VENDOR.REPO_URL

    def test_pin_records_exactly_the_expected_files(self) -> None:
        pin = json.loads(VENDOR.PIN_PATH.read_text(encoding="utf-8"))

        assert sorted(pin["files"]) == sorted(VENDOR.SCHEMA_FILES)

    def test_pinned_sha_is_a_full_commit_id(self) -> None:
        """A short SHA would let an ambiguous prefix satisfy the pin."""
        assert len(VENDOR.PINNED_SHA) == 40
        int(VENDOR.PINNED_SHA, 16)  # raises if not hex

    def test_offline_check_mode_passes_on_a_clean_tree(self) -> None:
        """_Requirements: 4.3 — the gate CI runs must pass when in sync._"""
        assert VENDOR.main(["--check"]) == 0

    def test_offline_check_detects_tampering(self, tmp_path: Path, monkeypatch) -> None:
        """_Requirements: 4.3 — non-zero exit when bytes no longer match._"""
        # Copy the vendored tree so the real one is never mutated by a test.
        sandbox = tmp_path / "1.0.0"
        sandbox.mkdir(parents=True)
        for name in [*VENDOR.SCHEMA_FILES, VENDOR.PIN_PATH.name]:
            (sandbox / name).write_bytes((VENDOR.VENDOR_DIR / name).read_bytes())

        monkeypatch.setattr(VENDOR, "VENDOR_DIR", sandbox)
        monkeypatch.setattr(VENDOR, "PIN_PATH", sandbox / "PIN.json")
        assert VENDOR.main(["--check"]) == 0  # baseline: the copy is clean

        target = sandbox / VENDOR.SCHEMA_FILES[0]
        target.write_bytes(target.read_bytes() + b"\n")

        assert VENDOR.main(["--check"]) == 1

    def test_offline_check_detects_a_missing_schema(self, tmp_path: Path, monkeypatch) -> None:
        sandbox = tmp_path / "1.0.0"
        sandbox.mkdir(parents=True)
        for name in [*VENDOR.SCHEMA_FILES, VENDOR.PIN_PATH.name]:
            (sandbox / name).write_bytes((VENDOR.VENDOR_DIR / name).read_bytes())
        monkeypatch.setattr(VENDOR, "VENDOR_DIR", sandbox)
        monkeypatch.setattr(VENDOR, "PIN_PATH", sandbox / "PIN.json")

        (sandbox / VENDOR.SCHEMA_FILES[0]).unlink()

        assert VENDOR.main(["--check"]) == 1

    def test_offline_check_detects_a_missing_pin(self, tmp_path: Path, monkeypatch) -> None:
        sandbox = tmp_path / "1.0.0"
        sandbox.mkdir(parents=True)
        for name in VENDOR.SCHEMA_FILES:
            (sandbox / name).write_bytes((VENDOR.VENDOR_DIR / name).read_bytes())
        monkeypatch.setattr(VENDOR, "VENDOR_DIR", sandbox)
        monkeypatch.setattr(VENDOR, "PIN_PATH", sandbox / "PIN.json")

        assert VENDOR.main(["--check"]) == 1

    def test_offline_check_needs_no_network(self, monkeypatch) -> None:
        """The CI gate must not be network-gated (that is the whole point)."""
        _block_sockets(monkeypatch)

        assert VENDOR.main(["--check"]) == 0


class TestVendoredSchemaContent:
    """_Requirements: 4.1 — the vendored files are the canonical schemas._"""

    @pytest.mark.parametrize("filename", VENDOR.SCHEMA_FILES)
    def test_is_valid_json(self, filename: str) -> None:
        json.loads((VENDOR.VENDOR_DIR / filename).read_text(encoding="utf-8"))

    @pytest.mark.parametrize("filename", VENDOR.SCHEMA_FILES)
    def test_is_a_valid_draft_2020_12_schema(self, filename: str) -> None:
        schema = json.loads((VENDOR.VENDOR_DIR / filename).read_text(encoding="utf-8"))

        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)  # raises on a malformed schema

    def test_plugin_schema_id_matches_the_registry_constant(self) -> None:
        schema = json.loads(
            (VENDOR.VENDOR_DIR / schema_registry.PLUGIN_SCHEMA_FILENAME).read_text(encoding="utf-8")
        )

        assert schema["$id"] == schema_registry.PLUGIN_SCHEMA_ID

    def test_mcp_schema_id_matches_the_registry_constant(self) -> None:
        schema = json.loads(
            (VENDOR.VENDOR_DIR / schema_registry.MCP_SCHEMA_FILENAME).read_text(encoding="utf-8")
        )

        assert schema["$id"] == schema_registry.MCP_SCHEMA_ID

    def test_schema_version_agrees_across_script_and_registry(self) -> None:
        assert VENDOR.SCHEMA_VERSION == schema_registry.SCHEMA_VERSION

    def test_vendor_dir_agrees_across_script_and_registry(self) -> None:
        """The script writes where the package reads."""
        from importlib.resources import files as package_files

        registry_dir = package_files("cli_agent_orchestrator.schemas")
        for part in ("agent_plugins", schema_registry.SCHEMA_VERSION):
            registry_dir = registry_dir / part

        assert Path(str(registry_dir)).resolve() == VENDOR.VENDOR_DIR.resolve()

    def test_manifest_schema_closes_additional_properties(self) -> None:
        """§5.2's closed manifest is what makes an unknown field detectable."""
        schema = schema_registry.load_schema(schema_registry.PLUGIN_SCHEMA_FILENAME)

        assert schema["additionalProperties"] is False
        assert sorted(schema["required"]) == ["$schema", "name"]


class TestMcpSchemaIsUnusedInIncrement1:
    """_Requirements: 11.3 — mcp.schema.json is committed but never validated._"""

    def test_mcp_schema_is_vendored(self) -> None:
        assert (VENDOR.VENDOR_DIR / schema_registry.MCP_SCHEMA_FILENAME).is_file()

    def test_registry_recognizes_no_mcp_schema_for_validation(self) -> None:
        """It must not be reachable through the recognized-schema mapping."""
        assert schema_registry.MCP_SCHEMA_ID not in schema_registry.RECOGNIZED_PLUGIN_SCHEMA_IDS
        assert not schema_registry.is_recognized_plugin_schema(schema_registry.MCP_SCHEMA_ID)

    def test_no_increment_1_module_builds_an_mcp_validator(self) -> None:
        """There is no callable that would validate against the MCP schema."""
        assert not hasattr(schema_registry, "mcp_config_validator")


def _block_sockets(monkeypatch) -> None:
    """Make any socket creation raise, proving no code path reaches the network."""

    def _refuse(*args: Any, **kwargs: Any):
        raise AssertionError("network access attempted; §5.2 forbids schema retrieval")

    monkeypatch.setattr(socket, "socket", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)


class TestOfflineValidation:
    """_Requirements: 4.4 — validation succeeds with all sockets blocked._"""

    def test_validator_builds_with_sockets_blocked(self, monkeypatch) -> None:
        schema_registry.load_schema.cache_clear()
        schema_registry.plugin_manifest_validator.cache_clear()
        schema_registry._registry.cache_clear()
        _block_sockets(monkeypatch)

        validator = schema_registry.plugin_manifest_validator()

        assert isinstance(validator, Draft202012Validator)

    def test_valid_manifest_validates_with_sockets_blocked(self, monkeypatch) -> None:
        schema_registry.load_schema.cache_clear()
        schema_registry.plugin_manifest_validator.cache_clear()
        schema_registry._registry.cache_clear()
        _block_sockets(monkeypatch)

        validator = schema_registry.plugin_manifest_validator()
        errors = list(
            validator.iter_errors(
                {
                    "$schema": schema_registry.PLUGIN_SCHEMA_ID,
                    "name": "example",
                    "version": "1.0.0",
                }
            )
        )

        assert errors == []

    def test_registry_refuses_to_retrieve_an_unvendored_ref(self) -> None:
        """An unresolvable $ref must raise, never become an HTTP request."""
        from referencing.exceptions import NoSuchResource

        with pytest.raises(NoSuchResource):
            schema_registry._refuse_retrieval("https://example.test/not-vendored.json")
