"""On-disk layout for installed Agent Plugins and their install records.

Layout::

    ~/.aws/cli-agent-orchestrator/
    ├── agent-plugins/
    │   ├── <plugin-name>/              # PLUGIN_ROOT — package bytes, never mutated
    │   └── .state/<plugin-name>.json   # install record (CAO-owned)
    ├── agent-plugin-data/<plugin-name>/ # PLUGIN_DATA (§9.1), survives updates
    └── skills/                          # existing SKILLS_DIR — projection target

``.state/`` is a **dot-prefixed sibling** so it is never mistaken for a plugin:
:meth:`InstalledPluginStore.list_installed` skips every name beginning with
``.``. That also makes crash-time staging directories (which are dot-prefixed
for the same reason) invisible to listing rather than half-installed plugins.

``PLUGIN_DATA`` lives **outside** ``AGENT_PLUGINS_DIR`` on purpose: §9.1 requires
its contents survive a plugin update, and an update replaces the plugin root
wholesale.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Optional

from cli_agent_orchestrator.agent_plugins.models import PluginRecord
from cli_agent_orchestrator.constants import AGENT_PLUGIN_DATA_DIR, AGENT_PLUGINS_DIR

logger = logging.getLogger(__name__)

# Owner-only, matching CAO_HOME_DIR's posture. When CAO_HOME_DIR is relocated
# outside ~/.aws there is no parent permission umbrella, and an installed plugin
# root is executable content in every sense that matters.
_DIR_MODE = 0o700

# Subdirectory of AGENT_PLUGINS_DIR holding install records.
_STATE_DIRNAME = ".state"


class PluginStoreError(RuntimeError):
    """Raised when the store cannot complete a publish or unpublish."""


def _ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) with owner-only permissions, idempotently."""
    path.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
    try:
        os.chmod(path, _DIR_MODE)
    except OSError:  # pragma: no cover - read-only mounts / foreign ownership
        pass
    return path


class InstalledPluginStore:
    """Owns the installed set and its install records.

    The store knows nothing about validation, resolution, or skill projection.
    It publishes bytes atomically and hands back records.
    """

    def __init__(
        self,
        plugins_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
    ) -> None:
        """Bind the store to its directories.

        Arguments default to the module-level constants and exist so tests (and
        any future multi-root use) can point a store at a scratch tree without
        re-importing ``constants``.
        """
        self._plugins_dir = Path(plugins_dir) if plugins_dir else AGENT_PLUGINS_DIR
        self._data_dir = Path(data_dir) if data_dir else AGENT_PLUGIN_DATA_DIR

    # ── locations ────────────────────────────────────────────────────────

    @property
    def plugins_dir(self) -> Path:
        """Root holding one directory per installed plugin."""
        return self._plugins_dir

    @property
    def data_dir(self) -> Path:
        """Root holding one ``PLUGIN_DATA`` directory per plugin."""
        return self._data_dir

    @property
    def state_dir(self) -> Path:
        """Directory holding ``<plugin-name>.json`` install records."""
        return self._plugins_dir / _STATE_DIRNAME

    def plugin_root(self, name: str) -> Path:
        """Return the ``PLUGIN_ROOT`` path for ``name`` (need not exist)."""
        return self._plugins_dir / _validate_plugin_dirname(name)

    def plugin_data_dir(self, name: str, *, create: bool = False) -> Path:
        """Return the ``PLUGIN_DATA`` path for ``name``, optionally creating it."""
        path = self._data_dir / _validate_plugin_dirname(name)
        if create:
            _ensure_dir(self._data_dir)
            _ensure_dir(path)
        return path

    def _record_path(self, name: str) -> Path:
        return self.state_dir / f"{_validate_plugin_dirname(name)}.json"

    # ── reads ────────────────────────────────────────────────────────────

    def list_installed(self) -> List[PluginRecord]:
        """Return every install record, sorted by plugin name.

        Sorted by ``name`` rather than returned in directory order because the
        projection engine's deterministic collision rule is a total order over
        plugin names; handing callers an already-ordered list means no caller
        can accidentally depend on ``os.scandir`` ordering.

        A record whose JSON is unreadable or malformed is logged and skipped
        rather than raising: listing is called from ``cao plugin list``, the web
        panel, and the projection rebuild, none of which may fail because one
        record got corrupted.
        """
        state_dir = self.state_dir
        if not state_dir.is_dir():
            return []

        records: List[PluginRecord] = []
        for entry in sorted(state_dir.iterdir(), key=lambda p: p.name):
            if entry.name.startswith(".") or entry.suffix != ".json" or not entry.is_file():
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
                records.append(PluginRecord.from_dict(data))
            except Exception as exc:
                logger.warning("Skipping unreadable agent-plugin record '%s': %s", entry, exc)
        return sorted(records, key=lambda record: record.name)

    def get(self, name: str) -> Optional[PluginRecord]:
        """Return one install record, or ``None`` when the plugin is not installed."""
        try:
            path = self._record_path(name)
        except ValueError:
            return None
        if not path.is_file():
            return None
        try:
            return PluginRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Unreadable agent-plugin record '%s': %s", path, exc)
            return None

    def is_installed(self, name: str) -> bool:
        """Whether a plugin root exists for ``name``."""
        try:
            return self.plugin_root(name).exists()
        except ValueError:
            return False

    # ── writes ───────────────────────────────────────────────────────────

    def publish(self, staged: Path, record: PluginRecord, *, force: bool = False) -> PluginRecord:
        """Move a validated staging tree into the store atomically.

        Uses the stage-then-rename pattern already proven in
        ``cli/commands/init.py::seed_default_skills()``: copy into a
        dot-prefixed temporary directory *inside* the destination's parent (so
        the rename is same-filesystem and therefore atomic), then rename into
        place. A process interruption at any point before the rename leaves the
        store byte-identical to its pre-publish state — which is the mechanism
        behind correctness property P4.

        ``force`` replaces an existing plugin of the same name. The replacement
        is *not* atomic end-to-end (POSIX cannot rename a directory over a
        non-empty directory), so the old root is moved aside first and only
        deleted once the new root is in place; a crash between the two leaves
        the old bytes recoverable in a dot-prefixed sibling rather than losing
        both.
        """
        name = _validate_plugin_dirname(record.name)
        _ensure_dir(self._plugins_dir)
        destination = self.plugin_root(name)

        if destination.exists() and not force:
            raise PluginStoreError(
                f"Agent plugin '{name}' is already installed. Use --force to replace it."
            )

        with TemporaryDirectory(prefix=f".{name}.", dir=self._plugins_dir) as staging_root:
            staged_copy = Path(staging_root) / name
            shutil.copytree(staged, staged_copy, symlinks=True)

            backup: Optional[Path] = None
            if destination.exists():
                backup = self._plugins_dir / f".{name}.replaced.{os.getpid()}"
                _rmtree_quiet(backup)
                destination.rename(backup)

            try:
                staged_copy.rename(destination)
            except OSError as exc:
                if backup is not None and not destination.exists():
                    # Put the previous bytes back. `not destination.exists()` is
                    # the concurrency guard: if something else published while we
                    # were mid-swap, restoring would clobber *its* tree, so the
                    # newer content is left alone and the old backup is dropped
                    # below instead.
                    try:
                        backup.rename(destination)
                    except OSError as restore_exc:
                        # The one case where a failure can destroy a working
                        # plugin: the aside-move succeeded, the swap failed, and
                        # now the restore has failed too. `destination` does not
                        # exist and this backup holds the only copy of the
                        # operator's bytes.
                        #
                        # `backup` is cleared *before* raising, which is the whole
                        # point: `finally` runs on the way out of an exception too,
                        # so leaving the variable set would delete the very
                        # directory this branch exists to preserve. The path is
                        # kept in a local for the message, because manual recovery
                        # is a single `mv` and an operator who is not told where
                        # to look cannot perform it.
                        preserved, backup = backup, None
                        raise PluginStoreError(
                            f"Agent plugin '{name}' could not be replaced, and the previous "
                            f"version could not be restored automatically ({restore_exc}). "
                            f"Its files are intact at {preserved} — move that directory back "
                            f"to {destination} to recover. Nothing was deleted."
                        ) from restore_exc
                    backup = None
                if exc.errno in (errno.EEXIST, errno.ENOTEMPTY):
                    raise PluginStoreError(
                        f"Agent plugin '{name}' was published concurrently; " f"re-run the install."
                    ) from exc
                raise
            finally:
                # Reached on success (the old tree is now redundant) and on a
                # failure that restored successfully (`backup` set to None above,
                # so nothing is deleted). The unrecoverable path raises before
                # here with `backup` deliberately left on disk.
                if backup is not None:
                    _rmtree_quiet(backup)

        self.write_record(record)
        return record

    def write_record(self, record: PluginRecord) -> Path:
        """Persist (or overwrite) one install record, atomically."""
        _ensure_dir(self._plugins_dir)
        _ensure_dir(self.state_dir)
        path = self._record_path(record.name)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(record.to_json(), encoding="utf-8")
        temp_path.replace(path)
        return path

    def unpublish(self, name: str, *, purge_data: bool = False) -> bool:
        """Remove a plugin's root and install record.

        ``purge_data`` defaults to ``False``: §9.1 says a client *MAY* delete
        ``PLUGIN_DATA`` on uninstall, and retaining it makes ``remove``
        non-destructive by default. ``cao plugin remove --purge-data`` opts in.
        Making the choice explicit rather than incidental is what makes the
        idempotence property (P5) decidable.

        Returns ``True`` when something was actually removed.
        """
        validated = _validate_plugin_dirname(name)
        removed = False

        root = self.plugin_root(validated)
        if root.exists() or root.is_symlink():
            _rmtree_quiet(root)
            removed = True

        record_path = self._record_path(validated)
        if record_path.exists():
            record_path.unlink()
            removed = True

        if purge_data:
            data_path = self.plugin_data_dir(validated)
            if data_path.exists():
                _rmtree_quiet(data_path)

        return removed


def _validate_plugin_dirname(name: str) -> str:
    """Reject any plugin name that could escape the store's directories.

    §5.5 already constrains manifest names to ``[a-z0-9.-]`` with no ``..``, and
    the validator enforces that. This is the second, independent guard applied
    at the point a name becomes a path — a store must not rely on its callers
    having validated, because ``get()``/``plugin_root()`` are also reachable
    from the CLI, the API, and install records written by an older version.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Agent plugin name must be a non-empty string")
    if name.startswith("."):
        raise ValueError(f"Agent plugin name must not start with '.': {name!r}")
    if "\x00" in name:
        raise ValueError(f"Agent plugin name must not contain a NUL byte: {name!r}")
    separators = {"/", "\\", os.sep}
    if os.altsep:
        separators.add(os.altsep)
    if any(sep in name for sep in separators):
        raise ValueError(f"Agent plugin name must not contain a path separator: {name!r}")
    if ".." in name:
        raise ValueError(f"Agent plugin name must not contain '..': {name!r}")
    return name


def _rmtree_quiet(path: Path) -> None:
    """Delete a path (file, symlink, or tree) without raising on absence."""
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError as exc:  # pragma: no cover - permissions / busy handles
        logger.warning("Could not remove '%s': %s", path, exc)
