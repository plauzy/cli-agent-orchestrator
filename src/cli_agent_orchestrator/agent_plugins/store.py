"""On-disk store for installed Agent Plugins.

Owns the layout and the two guarantees that layout exists to provide:

1. **Atomic publish.** A plugin becomes visible in one ``rename``, so an
   interruption mid-install leaves the store byte-identical to its prior state
   (Requirement 9.3). The stage-then-rename mechanics are lifted from
   ``seed_default_skills()``, including its ``errno.EEXIST/ENOTEMPTY`` race
   handling, because that code already solved this exact problem for skills.
2. **PLUGIN_DATA survives updates.** ``AGENT_PLUGIN_DATA_DIR`` is a sibling of
   ``AGENT_PLUGINS_DIR``, not a child, so replacing a PLUGIN_ROOT wholesale
   cannot touch persistent plugin state (§9.1, Requirement 22.6).

Layout::

    ~/.aws/cli-agent-orchestrator/
    ├── agent-plugins/
    │   ├── <plugin-name>/              # PLUGIN_ROOT — never mutated by CAO
    │   └── .state/<plugin-name>.json   # install record (CAO-owned)
    ├── agent-plugin-data/<plugin-name>/ # PLUGIN_DATA — survives updates
    └── skills/                          # existing SKILLS_DIR (projection target)

``.state/`` is dot-prefixed so it can never be mistaken for a plugin, the same
convention that lets ``seed_default_skills()`` stage under ``.<name>.`` inside
``SKILLS_DIR`` without a concurrent scan tripping over it.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from cli_agent_orchestrator.agent_plugins.models import PluginRecord
from cli_agent_orchestrator.constants import AGENT_PLUGIN_DATA_DIR, AGENT_PLUGINS_DIR
from cli_agent_orchestrator.utils.path_validation import safe_join_under_base

logger = logging.getLogger(__name__)

# Subdirectory holding CAO-owned install records. Dot-prefixed so that
# ``list_installed()``'s "skip names starting with '.'" rule excludes it
# without needing to special-case the name.
STATE_DIR_NAME = ".state"

# Ledger of which projected skill name currently belongs to which plugin.
#
# This is derived state, rebuilt from the installed set, but it must be
# *persisted* for two reasons neither of which the filesystem can answer:
#   1. In copy mode a projected skill is an ordinary directory, indistinguishable
#      from a user-added skill. Without a ledger, a rebuild could not tell its
#      own copies from skills it must never touch.
#   2. Detecting a winner reassignment (Requirement 14's transition warning)
#      needs the *previous* winner, which exists nowhere else once the link has
#      been replaced.
# Named with a ``.json`` suffix inside ``.state/``; a plugin literally named
# "projection" writes ``.state/projection.json`` too, so the ledger uses a
# dot-prefixed name that ``§5.5`` forbids a plugin from having.
PROJECTION_STATE_NAME = ".projection.json"

# Owner-only, matching CAO_HOME_DIR / TERMINAL_LOG_DIR / FIFO_DIR.
_DIR_MODE = 0o700


class PluginStoreError(RuntimeError):
    """A store operation could not be completed."""


def _ensure_private_dir(path: Path) -> Path:
    """Create ``path`` (and parents) owner-only, best-effort on the chmod.

    ``mkdir``'s ``mode`` is umask-masked and ignored entirely for a directory
    that already exists, so the explicit ``chmod`` is what actually enforces
    ``0o700``. It is best-effort for the same reason ``constants.py`` makes it
    best-effort: read-only mounts and non-owned directories must not turn a
    permission hardening step into a crash.
    """
    path.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
    try:
        os.chmod(path, _DIR_MODE)
    except OSError:
        pass  # best-effort: read-only mount or not owned by us
    return path


class InstalledPluginStore:
    """The set of installed plugins, as directories plus install records.

    ``plugins_dir`` and ``data_dir`` are injectable so tests can build a fresh,
    isolated store without relocating ``CAO_HOME_DIR`` for the whole process;
    production callers use the defaults.
    """

    def __init__(
        self,
        plugins_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
    ) -> None:
        self.plugins_dir = Path(plugins_dir) if plugins_dir is not None else AGENT_PLUGINS_DIR
        self.data_dir = Path(data_dir) if data_dir is not None else AGENT_PLUGIN_DATA_DIR

    # -- paths ---------------------------------------------------------------

    def plugin_root(self, name: str) -> Path:
        """Absolute PLUGIN_ROOT for ``name``, confined to the plugins dir.

        Routed through ``safe_join_under_base`` so a crafted name, or a
        pre-existing symlink at that path aiming outside the store, is rejected
        before any caller can read or write through it.
        """
        return Path(safe_join_under_base(str(self.plugins_dir), name, description="plugin name"))

    def plugin_data_dir(self, name: str, *, create: bool = False) -> Path:
        """Absolute PLUGIN_DATA for ``name``, confined to the data dir.

        ``create=False`` by default: callers that only need the path (display,
        removal checks) must not bring the directory into existence as a side
        effect of asking where it would be.
        """
        _ensure_private_dir(self.data_dir)
        path = Path(safe_join_under_base(str(self.data_dir), name, description="plugin name"))
        if create:
            _ensure_private_dir(path)
        return path

    def _state_dir(self, *, create: bool = False) -> Path:
        """Directory holding install records."""
        path = self.plugins_dir / STATE_DIR_NAME
        if create:
            _ensure_private_dir(self.plugins_dir)
            _ensure_private_dir(path)
        return path

    def record_path(self, name: str) -> Path:
        """Path of ``name``'s install record."""
        return Path(
            safe_join_under_base(
                str(self._state_dir()), f"{name}.json", description="plugin record name"
            )
        )

    # -- reads ---------------------------------------------------------------

    def list_installed(self) -> List[PluginRecord]:
        """Every installed plugin, sorted by name.

        Enumerates *directories*, not records, so a plugin whose record was
        lost is still reported rather than silently vanishing. Names beginning
        with ``.`` are skipped, which excludes both ``.state/`` and any
        ``.<name>.`` staging directory left behind by an interrupted publish.

        Sorted by name because the projection engine's collision rule is a
        total order on plugin name (Requirement 14.5); returning scan order here
        would let ``os.scandir`` leak into a decision that must not depend on
        it.
        """
        if not self.plugins_dir.is_dir():
            return []

        records: List[PluginRecord] = []
        for entry in sorted(self.plugins_dir.iterdir(), key=lambda item: item.name):
            if entry.name.startswith("."):
                continue
            if not entry.is_dir():
                continue
            record = self._read_record(entry.name)
            # A directory with no readable record is still an installed plugin.
            records.append(record if record is not None else PluginRecord(name=entry.name))
        return records

    def get(self, name: str) -> Optional[PluginRecord]:
        """The record for ``name``, or ``None`` if it is not installed.

        "Installed" means the PLUGIN_ROOT directory exists; the record is
        metadata about that fact, not the fact itself.
        """
        try:
            root = self.plugin_root(name)
        except ValueError:
            return None
        if not root.is_dir():
            return None
        record = self._read_record(name)
        return record if record is not None else PluginRecord(name=name)

    def _read_record(self, name: str) -> Optional[PluginRecord]:
        """Load and parse an install record, or ``None`` if unusable.

        Never raises: a corrupt or hand-edited record must degrade the metadata
        CAO can show, not break enumeration of the store.
        """
        try:
            path = self.record_path(name)
        except ValueError:
            return None
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable plugin record '%s': %s", path, exc)
            return None
        if not isinstance(data, dict):
            logger.warning("Ignoring malformed plugin record '%s': not an object", path)
            return None
        return PluginRecord.from_dict(data)

    # -- writes --------------------------------------------------------------

    def write_record(self, record: PluginRecord) -> None:
        """Persist an install record via temp-file + ``os.replace``.

        Atomic on purpose, unlike ``settings_service._save``'s plain write: a
        half-written record is indistinguishable from a corrupt one, and the
        projection engine's determinism depends on reading whole records.
        """
        self._state_dir(create=True)
        target = self.record_path(record.name)
        payload = json.dumps(record.to_dict(), indent=2, sort_keys=True)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{record.name}.", suffix=".json", dir=str(target.parent)
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temp_name, target)
        except BaseException:
            # Leave no partial record behind on any failure, including
            # KeyboardInterrupt — a stale temp file in .state/ would be read by
            # nobody but would linger forever.
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def projection_state_path(self) -> Path:
        """Path of the projection ledger."""
        return self._state_dir() / PROJECTION_STATE_NAME

    def read_projection(self) -> Dict[str, str]:
        """Load the ``skill name -> owning plugin name`` ledger.

        Never raises: a lost or corrupt ledger must degrade to "nothing is known
        to be projected", which a rebuild then corrects, rather than breaking
        install and removal entirely.
        """
        path = self.projection_state_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable projection ledger '%s': %s", path, exc)
            return {}
        if not isinstance(data, dict):
            return {}
        raw = data.get("projected")
        if not isinstance(raw, dict):
            return {}
        return {
            str(skill): str(plugin)
            for skill, plugin in raw.items()
            if isinstance(skill, str) and isinstance(plugin, str) and skill and plugin
        }

    def write_projection(self, projected: Dict[str, str]) -> None:
        """Persist the projection ledger atomically."""
        self._state_dir(create=True)
        target = self.projection_state_path()
        payload = json.dumps(
            {"projected": dict(sorted(projected.items()))}, indent=2, sort_keys=True
        )
        handle, temp_name = tempfile.mkstemp(
            prefix=".projection.", suffix=".json", dir=str(target.parent)
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temp_name, target)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def publish(self, staged: Path, record: PluginRecord, *, force: bool = False) -> PluginRecord:
        """Publish ``staged`` as ``record.name``'s PLUGIN_ROOT, atomically.

        The staged tree usually lives on another filesystem (the resolver
        stages into a temp dir), so it is first copied into a dot-prefixed
        staging directory *inside* ``plugins_dir`` — that makes the final
        ``rename`` same-filesystem and therefore atomic, exactly as
        ``seed_default_skills()`` does by passing ``dir=SKILLS_DIR``.

        Raises:
            FileExistsError: ``name`` is already installed and ``force`` is
                not set. Mirrors ``_install_skill_folder``'s refuse-unless-force
                contract in ``cli/commands/skills.py``.
            PluginStoreError: the staged directory is unusable.
        """
        staged = Path(staged)
        if not staged.is_dir():
            raise PluginStoreError(f"staged plugin directory does not exist: {staged}")

        _ensure_private_dir(self.plugins_dir)
        destination = self.plugin_root(record.name)

        if destination.exists() or destination.is_symlink():
            if not force:
                raise FileExistsError(
                    f"Plugin '{record.name}' is already installed. " f"Use --force to replace it."
                )

        with tempfile.TemporaryDirectory(
            prefix=f".{record.name}.", dir=str(self.plugins_dir)
        ) as staging_root:
            incoming = Path(staging_root) / record.name
            # symlinks=True: a plugin's own internal symlinks are part of its
            # bytes, and §4.1 permits those resolving inside the root. Copying
            # them as links rather than dereferencing keeps the published tree
            # byte-faithful and preserves what containment already vetted.
            shutil.copytree(staged, incoming, symlinks=True)

            if not (destination.exists() or destination.is_symlink()):
                try:
                    incoming.rename(destination)
                except OSError as exc:
                    # Lost a race with a concurrent publisher of the same name.
                    if exc.errno in (errno.EEXIST, errno.ENOTEMPTY) and destination.exists():
                        if not force:
                            raise FileExistsError(
                                f"Plugin '{record.name}' is already installed. "
                                f"Use --force to replace it."
                            ) from exc
                        self._replace(incoming, destination)
                    else:
                        raise
            else:
                self._replace(incoming, destination)

        self.write_record(record)
        return record

    def _replace(self, incoming: Path, destination: Path) -> None:
        """Swap ``incoming`` into ``destination``, retiring the old tree.

        ``rename`` onto a non-empty directory fails with ``ENOTEMPTY``, so the
        old tree is first moved aside within the same directory (one rename),
        then the new tree is renamed in (a second rename), then the old tree is
        deleted. The window between the two renames is the only moment
        ``destination`` does not exist; if the second rename fails the old tree
        is put back, so a failed replace never destroys a working plugin.
        """
        retired = Path(
            tempfile.mkdtemp(prefix=f".retired.{destination.name}.", dir=str(destination.parent))
        )
        retired_tree = retired / destination.name
        os.rename(destination, retired_tree)
        try:
            incoming.rename(destination)
        except OSError:
            os.rename(retired_tree, destination)  # restore the previous tree
            shutil.rmtree(retired, ignore_errors=True)
            raise
        shutil.rmtree(retired, ignore_errors=True)

    def unpublish(self, name: str, *, purge_data: bool = False) -> None:
        """Remove ``name``'s PLUGIN_ROOT and install record.

        ``purge_data`` defaults to ``False``: §9.1 says a client *MAY* delete
        PLUGIN_DATA on uninstall, and retaining it makes ``remove``
        non-destructive by default (Requirement 10.4). Opting in is what
        ``--purge-data`` is for (Requirement 10.3).

        Idempotent — removing something absent is a success, which is what
        makes the idempotence property decidable.
        """
        try:
            root = self.plugin_root(name)
        except ValueError as exc:
            raise PluginStoreError(f"invalid plugin name {name!r}: {exc}") from exc

        if root.is_symlink():
            root.unlink()
        elif root.exists():
            shutil.rmtree(root)

        try:
            record = self.record_path(name)
        except ValueError:
            record = None
        if record is not None and record.exists():
            record.unlink()

        if purge_data:
            data_dir = self.plugin_data_dir(name)
            if data_dir.exists():
                shutil.rmtree(data_dir, ignore_errors=True)
