#!/usr/bin/env python3
"""Vendor the pinned Agent Plugins JSON schemas into CAO's package tree.

Why this exists
---------------
Agent Plugins §5.2 forbids a client from *retrieving* a schema while loading a
plugin. CAO therefore validates against schema files committed inside this
repository, and this script is what puts them there and proves they are the
bytes we think they are.

Design invariants (mirroring ``scripts/vendor_ext_apps_skills.py``)
-------------------------------------------------------------------
* **Pinned, not floating.** ``PINNED_REF`` plus ``PINNED_SHA`` name an exact
  upstream commit. A retagged or force-pushed upstream is caught, because the
  resolved ``HEAD`` must equal ``PINNED_SHA``.
* **Idempotent.** Refreshing replaces the vendored files wholesale, so no stale
  file can survive a schema being removed upstream.
* **Hash-manifested.** ``PIN.json`` records the sha256 of every vendored file.
  This is a deliberate strengthening over ``vendor_ext_apps_skills.py``, which
  relies on the commit SHA plus a ``filecmp`` tree diff and therefore cannot
  verify anything without network access.

The ``--check`` contract (this is the important difference)
----------------------------------------------------------
``--check`` is **fully offline**: it recomputes the sha256 of each vendored file
and compares it to ``PIN.json``. That matters because CAO's CI must run this
gate on *every* pull request, and a gate that silently degrades to
"unverifiable" whenever the network is unavailable is not a gate. Verifying the
bytes against a committed hash manifest needs no network, so ``--check`` has no
network-gated escape hatch and only ever exits 0 or 1.

``--check-upstream`` is the separate, network-touching check: it additionally
re-clones the pin and confirms the vendored bytes still match upstream at
``PINNED_SHA``. That one *can* be network-gated, and exits 2 when it is.

Exit codes
----------
=====  =========================================================
    0  in sync (or refreshed successfully)
    1  verified drift — vendored bytes do not match the manifest
    2  unverifiable — upstream unreachable, or git missing
=====  =========================================================

Usage
-----
    python scripts/vendor_agent_plugins_schemas.py                  # refresh
    python scripts/vendor_agent_plugins_schemas.py --check          # offline gate
    python scripts/vendor_agent_plugins_schemas.py --check-upstream  # + network
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# --- Pin -------------------------------------------------------------------
# Upstream source and the exact commit this vendored copy is taken from.
# Bump REF and SHA together when refreshing; they must agree or the script
# aborts. The repository publishes no tags, so the ref is the default branch
# and PINNED_SHA is the only thing that actually pins the content.
REPO_URL = "https://github.com/agentplugins/agent-plugins-spec.git"
PINNED_REF = "main"
PINNED_SHA = "bd383552095128f6effe895b9257cfd580a6d179"

# Agent Plugins version whose schemas we vendor.
SCHEMA_VERSION = "1.0.0"

# Path inside the upstream repo holding that version's schemas.
UPSTREAM_SCHEMAS_SUBPATH = f"schemas/{SCHEMA_VERSION}"

# The schema files we vendor.
#
# ``mcp.schema.json`` is committed but DELIBERATELY UNUSED in Increment 1:
# Requirement 11.3 forbids any Increment 1 code path from validating against
# it. It is vendored now so that the pin, the hash manifest, and the CI gate
# cover it from the start, and Increment 2 adds only the code that reads it.
SCHEMA_FILES: List[str] = [
    "plugin.schema.json",
    "mcp.schema.json",
]

# --- Local layout ----------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT / "src" / "cli_agent_orchestrator" / "schemas" / "agent_plugins" / SCHEMA_VERSION
PIN_PATH = VENDOR_DIR / "PIN.json"

# Remediation hint printed on any drift, so the failure tells you the fix.
REFRESH_COMMAND = "python scripts/vendor_agent_plugins_schemas.py"


class VendorError(RuntimeError):
    """A non-recoverable failure reaching or verifying the pin."""


def _display(path: Path) -> str:
    """Render ``path`` repo-relative when possible, absolute otherwise.

    ``Path.relative_to`` raises for a path outside ``ROOT``, and a crash inside
    an error-reporting branch would replace a clear diagnostic with a traceback.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _run_git(args: List[str], cwd: Optional[Path] = None) -> str:
    """Run ``git`` with ``args``, returning stripped stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment-dependent
        raise VendorError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise VendorError(
            f"git {' '.join(args)} failed (exit {exc.returncode}): {exc.stderr.strip()}"
        ) from exc
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    """Hex sha256 of a file's bytes."""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _clone_pinned(dest: Path) -> str:
    """Shallow, blobless, sparse clone of the pin; returns the resolved SHA."""
    _run_git(
        [
            "clone",
            "--depth",
            "1",
            "--branch",
            PINNED_REF,
            "--filter=blob:none",
            "--sparse",
            REPO_URL,
            str(dest),
        ]
    )
    _run_git(["sparse-checkout", "set", UPSTREAM_SCHEMAS_SUBPATH], cwd=dest)

    resolved = _run_git(["rev-parse", "HEAD"], cwd=dest)
    if resolved != PINNED_SHA:
        raise VendorError(
            f"Pin mismatch: ref {PINNED_REF!r} resolved to {resolved}, "
            f"expected {PINNED_SHA}. Refresh the pin deliberately "
            f"(update PINNED_REF/PINNED_SHA) if this is intentional."
        )
    return resolved


def _upstream_schema_file(repo: Path, filename: str) -> Path:
    """Locate one schema file upstream, guarding against a layout change."""
    path = repo / UPSTREAM_SCHEMAS_SUBPATH / filename
    if not path.is_file():
        raise VendorError(
            f"Upstream schema not found at {UPSTREAM_SCHEMAS_SUBPATH}/{filename}. "
            f"Upstream layout may have changed."
        )
    return path


def _render_pin(sha: str, hashes: Dict[str, str]) -> str:
    """Render ``PIN.json``.

    Deterministic (no timestamps): ``--check`` diffs against it, so anything
    varying between runs would make the manifest unverifiable.
    """
    payload = {
        "_comment": (
            "Provenance for the vendored Agent Plugins schemas. Generated by "
            "scripts/vendor_agent_plugins_schemas.py -- do not hand-edit. "
            "Agent Plugins 5.2 forbids retrieving a schema at validation time, "
            "so these bytes are the only schemas CAO ever validates against."
        ),
        "source_url": REPO_URL,
        "ref": PINNED_REF,
        "commit": sha,
        "schema_version": SCHEMA_VERSION,
        "upstream_subpath": UPSTREAM_SCHEMAS_SUBPATH,
        "files": {name: {"sha256": hashes[name]} for name in sorted(hashes)},
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _load_pin() -> Dict[str, object]:
    """Read and structurally validate ``PIN.json``."""
    if not PIN_PATH.is_file():
        raise VendorError(f"pin manifest missing: {_display(PIN_PATH)}")
    try:
        data = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise VendorError(f"pin manifest is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise VendorError("pin manifest is not a JSON object")
    if not isinstance(data.get("files"), dict):
        raise VendorError("pin manifest has no 'files' object")
    return data


def _vendor(repo: Path, sha: str) -> None:
    """Copy the pinned schemas in and rewrite the hash manifest."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    # Remove vendored files no longer in SCHEMA_FILES so a schema deleted
    # upstream cannot linger and keep validating.
    expected = set(SCHEMA_FILES)
    for existing in VENDOR_DIR.glob("*.json"):
        if existing.name != PIN_PATH.name and existing.name not in expected:
            existing.unlink()

    hashes: Dict[str, str] = {}
    for filename in SCHEMA_FILES:
        source = _upstream_schema_file(repo, filename)
        destination = VENDOR_DIR / filename
        # write_bytes, not copy: the vendored file must be byte-identical to
        # the canonical published schema, with no newline or mode translation.
        destination.write_bytes(source.read_bytes())
        hashes[filename] = _sha256(destination)

    PIN_PATH.write_text(_render_pin(sha, hashes), encoding="utf-8")


def _check_offline() -> int:
    """Verify vendored bytes against ``PIN.json``. No network required."""
    problems: List[str] = []

    try:
        pin = _load_pin()
    except VendorError as exc:
        print(f"Vendored Agent Plugins schemas are UNVERIFIABLE: {exc}", file=sys.stderr)
        print(f"\nRun: {REFRESH_COMMAND}  (then commit the result)", file=sys.stderr)
        return 1

    recorded = pin["files"]
    assert isinstance(recorded, dict)  # guaranteed by _load_pin

    if pin.get("commit") != PINNED_SHA:
        problems.append(
            f"PIN.json commit {pin.get('commit')!r} does not match "
            f"PINNED_SHA {PINNED_SHA!r} in this script"
        )
    if pin.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"PIN.json schema_version {pin.get('schema_version')!r} does not match "
            f"SCHEMA_VERSION {SCHEMA_VERSION!r}"
        )

    for filename in SCHEMA_FILES:
        path = VENDOR_DIR / filename
        if not path.is_file():
            problems.append(f"vendored schema missing: {_display(path)}")
            continue

        entry = recorded.get(filename)
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            problems.append(f"no recorded sha256 for {filename}")
            continue

        actual = _sha256(path)
        if actual != entry["sha256"]:
            problems.append(
                f"content differs: {filename} hashes to {actual}, "
                f"PIN.json records {entry['sha256']}"
            )

        # A schema that is not parseable JSON would fail at validation time
        # rather than here, which is far harder to diagnose.
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"not valid JSON: {filename} ({exc})")

    for extra in sorted(recorded):
        if extra not in SCHEMA_FILES:
            problems.append(f"PIN.json records an unexpected file: {extra}")

    if problems:
        print("Vendored Agent Plugins schemas are OUT OF SYNC with the pin:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(f"\nRun: {REFRESH_COMMAND}  (then commit the result)", file=sys.stderr)
        return 1

    print(
        f"OK: {len(SCHEMA_FILES)} vendored Agent Plugins {SCHEMA_VERSION} schemas "
        f"match PIN.json ({PINNED_SHA[:12]})"
    )
    return 0


def _check_upstream(repo: Path) -> int:
    """Verify vendored bytes still match upstream at ``PINNED_SHA``."""
    problems: List[str] = []
    for filename in SCHEMA_FILES:
        upstream = _upstream_schema_file(repo, filename)
        vendored = VENDOR_DIR / filename
        if not vendored.is_file():
            problems.append(f"vendored schema missing: {_display(vendored)}")
            continue
        if _sha256(upstream) != _sha256(vendored):
            problems.append(f"content differs from upstream: {filename}")

    if problems:
        print(
            f"Vendored Agent Plugins schemas DIVERGE from upstream at {PINNED_SHA[:12]}:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(f"\nRun: {REFRESH_COMMAND}  (then commit the result)", file=sys.stderr)
        return 1

    print(f"OK: vendored schemas match upstream at {PINNED_SHA[:12]}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify vendored bytes against PIN.json. Offline; exits 0 or 1.",
    )
    parser.add_argument(
        "--check-upstream",
        action="store_true",
        help="Also re-clone the pin and compare bytes to upstream (needs network).",
    )
    args = parser.parse_args(argv)

    # The offline gate never needs git or the network, so run it first and
    # return immediately — this is the path CI takes on every pull request.
    if args.check and not args.check_upstream:
        return _check_offline()

    with tempfile.TemporaryDirectory(prefix="agent-plugins-schemas-") as tmp:
        repo = Path(tmp) / "agent-plugins-spec"
        try:
            sha = _clone_pinned(repo)
        except VendorError as exc:
            print(f"Agent Plugins schema pin could not be reached: {exc}", file=sys.stderr)
            if args.check_upstream:
                print(
                    "Skipping --check-upstream (network-gated). Run "
                    "'--check' for the offline hash verification, which is "
                    "authoritative for CI.",
                    file=sys.stderr,
                )
                return 2
            print(
                f"Vendoring requires network access to {REPO_URL} at "
                f"{PINNED_REF}. Run this where the network is available, then "
                f"commit {_display(VENDOR_DIR)}/.",
                file=sys.stderr,
            )
            return 2

        if args.check_upstream:
            # Byte-vs-upstream and byte-vs-manifest are independent failures;
            # report both rather than letting the first mask the second.
            upstream_status = _check_upstream(repo)
            offline_status = _check_offline()
            return upstream_status or offline_status

        _vendor(repo, sha)

    print(
        f"Vendored {len(SCHEMA_FILES)} Agent Plugins {SCHEMA_VERSION} schemas "
        f"from {PINNED_REF} ({PINNED_SHA[:12]}) into "
        f"{_display(VENDOR_DIR)}/"
    )
    print(f"Recorded sha256 for each file in {_display(PIN_PATH)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
