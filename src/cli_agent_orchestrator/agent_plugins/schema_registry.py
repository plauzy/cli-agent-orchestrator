"""Access to the vendored, pinned Agent Plugins JSON schemas.

§5.2 forbids a client from retrieving a schema while loading a plugin. Honouring
that is not simply "don't call requests" — ``jsonschema`` will resolve an
unrecognized ``$ref`` over the network *by default*, so an innocuous-looking
schema edit could silently reintroduce a fetch. This module therefore does two
things:

1. Reads schema bytes only from the vendored package resources, via
   ``importlib.resources`` (so it works identically from a wheel, an editable
   install, and a zipimport).
2. Builds every validator against a ``referencing`` registry whose retrieval
   callback **raises**. A ``$ref`` CAO has not vendored becomes a loud error
   instead of a quiet HTTP request.

Requirement 4.4 / Property P11 assert this directly: with all sockets blocked,
validation of a valid plugin must still succeed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files as _package_files
from typing import Any, Dict

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

# The Agent Plugins version whose schemas are vendored. Kept in lockstep with
# scripts/vendor_agent_plugins_schemas.py's SCHEMA_VERSION by a test.
SCHEMA_VERSION = "1.0.0"

# Package path holding the vendored schema tree.
_SCHEMA_PACKAGE = "cli_agent_orchestrator.schemas"
_SCHEMA_SUBPATH = ("agent_plugins", SCHEMA_VERSION)

PLUGIN_SCHEMA_FILENAME = "plugin.schema.json"
MCP_SCHEMA_FILENAME = "mcp.schema.json"
PIN_FILENAME = "PIN.json"

# The canonical ``$schema`` identifier a conformant 1.0.0 manifest must declare
# (§5.3). This is the *only* value CAO recognizes; §5.2 requires rejecting an
# unrecognized one rather than guessing or fetching it.
PLUGIN_SCHEMA_ID = f"https://agent-plugins.org/schemas/{SCHEMA_VERSION}/plugin.schema.json"
MCP_SCHEMA_ID = f"https://agent-plugins.org/schemas/{SCHEMA_VERSION}/mcp.schema.json"

# Every schema identifier CAO can validate against, mapped to its vendored
# file. Membership in this mapping is what "recognized" means.
RECOGNIZED_PLUGIN_SCHEMA_IDS: Dict[str, str] = {
    PLUGIN_SCHEMA_ID: PLUGIN_SCHEMA_FILENAME,
}


class SchemaUnavailableError(RuntimeError):
    """A vendored schema could not be read or parsed.

    This is a CAO packaging fault, not a plugin fault — it means the wheel is
    missing files the drift guard should have caught.
    """


def _read_vendored(filename: str) -> str:
    """Read a vendored schema file's text from package resources."""
    resource = _package_files(_SCHEMA_PACKAGE)
    for part in _SCHEMA_SUBPATH:
        resource = resource / part
    try:
        return (resource / filename).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise SchemaUnavailableError(
            f"vendored Agent Plugins schema {filename!r} is missing from this "
            f"installation; run 'make refresh-agent-plugins-schemas'"
        ) from exc


@lru_cache(maxsize=None)
def load_schema(filename: str) -> Dict[str, Any]:
    """Parse and cache one vendored schema.

    Cached because validation runs per plugin and the bytes are immutable for
    the process's lifetime.
    """
    raw = _read_vendored(filename)
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise SchemaUnavailableError(
            f"vendored Agent Plugins schema {filename!r} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise SchemaUnavailableError(
            f"vendored Agent Plugins schema {filename!r} is not a JSON object"
        )
    return parsed


def load_pin() -> Dict[str, Any]:
    """Parse the vendored ``PIN.json`` provenance manifest."""
    parsed = load_schema(PIN_FILENAME)
    return parsed


def _refuse_retrieval(uri: str) -> Resource[Any]:
    """Registry retriever that refuses every lookup.

    This is the enforcement point for §5.2. Any ``$ref`` not already in the
    registry lands here and raises, so no code path can turn schema resolution
    into network I/O.
    """
    # ``referencing`` builds these constructors with attrs, whose generated
    # signatures mypy cannot see; both keywords are correct at runtime and are
    # covered by tests in test_schema_pin_property.py.
    raise NoSuchResource(ref=uri)  # type: ignore[call-arg]


@lru_cache(maxsize=None)
def _registry() -> Registry[Any]:
    """Registry pre-loaded with the vendored schemas and nothing else."""
    resources = []
    for schema_id, filename in RECOGNIZED_PLUGIN_SCHEMA_IDS.items():
        resources.append((schema_id, Resource.from_contents(load_schema(filename))))
    registry: Registry[Any] = Registry(  # type: ignore[call-arg]
        retrieve=_refuse_retrieval
    ).with_resources(resources)
    return registry


@lru_cache(maxsize=None)
def plugin_manifest_validator() -> Draft202012Validator:
    """Validator for ``plugin.json``, wired to refuse remote retrieval."""
    return Draft202012Validator(
        load_schema(PLUGIN_SCHEMA_FILENAME),
        registry=_registry(),
    )


def is_recognized_plugin_schema(schema_id: Any) -> bool:
    """Whether ``schema_id`` names a locally pinned plugin schema (§5.2)."""
    return isinstance(schema_id, str) and schema_id in RECOGNIZED_PLUGIN_SCHEMA_IDS
