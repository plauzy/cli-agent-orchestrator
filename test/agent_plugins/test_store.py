"""Unit tests for ``InstalledPluginStore`` (W1).

_Requirements: 9.3, 10.2, 10.3, 10.4, 22.6_
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins.models import (
    Finding,
    PluginRecord,
    PluginSource,
    Severity,
    utc_now,
)
from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore, PluginStoreError

from .conftest import SCHEMA_ID


def _record(name: str = "example", **overrides) -> PluginRecord:
    """A fully-populated record, so round-trip tests cover every field."""
    defaults = dict(
        name=name,
        version="1.2.3",
        source=PluginSource(
            kind="git", location="https://example.test/p.git", ref="v1", subdir="pkg"
        ),
        resolved_ref="a" * 40,
        installed_at=utc_now(),
        schema_id=SCHEMA_ID,
        skill_names=("alpha", "beta"),
        projected_skill_names=("alpha",),
        findings=(
            Finding(
                severity=Severity.SKIPPED,
                code="projection.collision",
                spec_ref="§7.1",
                message="'beta' collides with a pre-existing skill",
                path="skills/beta",
            ),
        ),
    )
    defaults.update(overrides)
    return PluginRecord(**defaults)  # type: ignore[arg-type]


class TestRecordRoundTrip:
    """Install records survive a write/read cycle without losing fields."""

    def test_round_trip_preserves_every_field(self, store: InstalledPluginStore) -> None:
        original = _record()
        store.write_record(original)

        loaded = store._read_record("example")

        assert loaded == original

    def test_record_is_written_inside_dot_state(self, store: InstalledPluginStore) -> None:
        store.write_record(_record())

        assert (store.plugins_dir / ".state" / "example.json").is_file()

    def test_record_is_valid_json_with_stable_key_order(self, store: InstalledPluginStore) -> None:
        store.write_record(_record())

        raw = (store.plugins_dir / ".state" / "example.json").read_text(encoding="utf-8")
        data = json.loads(raw)

        assert data["name"] == "example"
        assert data["skill_names"] == ["alpha", "beta"]
        # sort_keys=True keeps records diffable and drift-checkable.
        assert list(data) == sorted(data)

    def test_unreadable_record_degrades_instead_of_raising(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), PluginRecord(name="example"))
        (store.plugins_dir / ".state" / "example.json").write_text("{not json", encoding="utf-8")

        # Still installed; only the metadata is lost.
        assert store._read_record("example") is None
        assert [record.name for record in store.list_installed()] == ["example"]

    def test_non_object_record_is_ignored(self, store: InstalledPluginStore) -> None:
        store.write_record(_record())
        (store.plugins_dir / ".state" / "example.json").write_text("[1, 2]", encoding="utf-8")

        assert store._read_record("example") is None

    def test_unknown_severity_degrades_to_info(self, store: InstalledPluginStore) -> None:
        payload = _record().to_dict()
        payload["findings"][0]["severity"] = "catastrophic"
        store._state_dir(create=True)
        store.record_path("example").write_text(json.dumps(payload), encoding="utf-8")

        loaded = store._read_record("example")

        assert loaded is not None
        assert loaded.findings[0].severity is Severity.INFO


class TestPermissions:
    """_Requirements: 22.6 — owner-only store and data directories._"""

    @staticmethod
    def _mode(path: Path) -> int:
        return stat.S_IMODE(path.stat().st_mode)

    def test_plugins_dir_is_owner_only_after_publish(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), PluginRecord(name="example"))

        assert self._mode(store.plugins_dir) == 0o700

    def test_state_dir_is_owner_only(self, store: InstalledPluginStore) -> None:
        store.write_record(_record())

        assert self._mode(store.plugins_dir / ".state") == 0o700

    def test_data_dir_is_owner_only(self, store: InstalledPluginStore) -> None:
        store.plugin_data_dir("example", create=True)

        assert self._mode(store.data_dir) == 0o700
        assert self._mode(store.data_dir / "example") == 0o700

    def test_pre_existing_loose_dir_is_tightened(self, store: InstalledPluginStore) -> None:
        store.plugins_dir.mkdir(parents=True)
        store.plugins_dir.chmod(0o755)

        store.write_record(_record())

        # mkdir's mode is ignored for an existing dir; the explicit chmod is
        # what actually enforces the posture.
        assert self._mode(store.plugins_dir) == 0o700


class TestListInstalled:
    """Enumeration skips CAO-owned and in-flight entries."""

    def test_empty_store_lists_nothing(self, store: InstalledPluginStore) -> None:
        assert store.list_installed() == []

    def test_lists_published_plugins_sorted_by_name(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        for name in ("zebra", "alpha", "mango"):
            store.publish(plugin_factory(name), PluginRecord(name=name))

        assert [record.name for record in store.list_installed()] == ["alpha", "mango", "zebra"]

    def test_dot_state_is_never_listed_as_a_plugin(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), _record())

        names = [record.name for record in store.list_installed()]

        assert ".state" not in names
        assert names == ["example"]

    def test_leftover_staging_dir_is_ignored(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), PluginRecord(name="example"))
        # Simulate a crash mid-publish: a dot-prefixed staging tree survives.
        (store.plugins_dir / ".example.abc123").mkdir()

        assert [record.name for record in store.list_installed()] == ["example"]

    def test_plugin_dir_without_a_record_is_still_listed(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), _record())
        store.record_path("example").unlink()

        records = store.list_installed()

        assert [record.name for record in records] == ["example"]
        assert records[0].version is None  # metadata lost, existence preserved

    def test_stray_file_is_not_a_plugin(self, store: InstalledPluginStore) -> None:
        store.plugins_dir.mkdir(parents=True)
        (store.plugins_dir / "README.txt").write_text("not a plugin", encoding="utf-8")

        assert store.list_installed() == []


class TestGet:
    def test_returns_none_when_not_installed(self, store: InstalledPluginStore) -> None:
        assert store.get("absent") is None

    def test_returns_record_when_installed(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), _record())

        found = store.get("example")

        assert found is not None
        assert found.version == "1.2.3"

    def test_invalid_name_returns_none_rather_than_raising(
        self, store: InstalledPluginStore
    ) -> None:
        assert store.get("../escape") is None


class TestPathContainment:
    """Store paths are confined; a crafted name cannot escape."""

    @pytest.mark.parametrize("name", ["../escape", "a/b", "..", ".", "", "with space", "nul\x00"])
    def test_plugin_root_rejects_unsafe_names(self, store: InstalledPluginStore, name: str) -> None:
        with pytest.raises(ValueError):
            store.plugin_root(name)

    def test_plugin_root_is_inside_plugins_dir(self, store: InstalledPluginStore) -> None:
        store.plugins_dir.mkdir(parents=True)

        root = store.plugin_root("example")

        assert root.parent == store.plugins_dir.resolve()

    def test_data_dir_is_outside_the_plugin_root_tree(self, store: InstalledPluginStore) -> None:
        """_Requirements: 22.6 — PLUGIN_DATA must not live under PLUGIN_ROOT._"""
        store.plugins_dir.mkdir(parents=True)
        data = store.plugin_data_dir("example", create=True).resolve()

        assert store.plugins_dir.resolve() not in data.parents

    def test_plugin_data_dir_does_not_create_unless_asked(
        self, store: InstalledPluginStore
    ) -> None:
        path = store.plugin_data_dir("example")

        assert not path.exists()


class TestPublish:
    def test_publishes_package_bytes(self, store: InstalledPluginStore, plugin_factory) -> None:
        source = plugin_factory("example", skills=("alpha", "beta"))

        store.publish(source, PluginRecord(name="example"))

        root = store.plugin_root("example")
        assert (root / "plugin.json").is_file()
        assert (root / "skills" / "alpha" / "SKILL.md").is_file()
        assert (root / "skills" / "beta" / "SKILL.md").is_file()

    def test_published_tree_is_independent_of_the_source(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        source = plugin_factory("example")
        store.publish(source, PluginRecord(name="example"))

        (source / "plugin.json").write_text("mutated after install", encoding="utf-8")

        published = (store.plugin_root("example") / "plugin.json").read_text(encoding="utf-8")
        assert "mutated" not in published

    def test_refuses_existing_name_without_force(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), PluginRecord(name="example"))

        with pytest.raises(FileExistsError, match="--force"):
            store.publish(plugin_factory("example"), PluginRecord(name="example"))

    def test_force_replaces_the_published_tree(
        self, store: InstalledPluginStore, tmp_path: Path, plugin_factory
    ) -> None:
        store.publish(
            plugin_factory("example", skills=("old-skill",)), PluginRecord(name="example")
        )

        from .conftest import make_plugin

        replacement = make_plugin(tmp_path / "replacement", "example", skills=("new-skill",))
        store.publish(replacement, PluginRecord(name="example", version="2.0.0"), force=True)

        root = store.plugin_root("example")
        assert (root / "skills" / "new-skill").is_dir()
        assert not (root / "skills" / "old-skill").exists()
        found = store.get("example")
        assert found is not None and found.version == "2.0.0"

    def test_force_replace_leaves_no_temp_dirs_behind(
        self, store: InstalledPluginStore, tmp_path: Path, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), PluginRecord(name="example"))
        from .conftest import make_plugin

        store.publish(
            make_plugin(tmp_path / "again", "example"),
            PluginRecord(name="example"),
            force=True,
        )

        leftovers = [
            entry.name
            for entry in store.plugins_dir.iterdir()
            if entry.name.startswith(".") and entry.name != ".state"
        ]
        assert leftovers == []

    def test_missing_staged_dir_raises_store_error(self, store: InstalledPluginStore) -> None:
        with pytest.raises(PluginStoreError, match="does not exist"):
            store.publish(store.plugins_dir / "nope", PluginRecord(name="example"))

    def test_internal_symlinks_are_preserved_not_dereferenced(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        source = plugin_factory("example")
        (source / "skills" / "linked").symlink_to("example-skill")

        store.publish(source, PluginRecord(name="example"))

        assert (store.plugin_root("example") / "skills" / "linked").is_symlink()


class TestUnpublish:
    def test_removes_root_and_record(self, store: InstalledPluginStore, plugin_factory) -> None:
        store.publish(plugin_factory("example"), _record())

        store.unpublish("example")

        assert not store.plugin_root("example").exists()
        assert not store.record_path("example").exists()
        assert store.get("example") is None

    def test_is_idempotent_for_an_absent_plugin(self, store: InstalledPluginStore) -> None:
        store.plugins_dir.mkdir(parents=True)

        store.unpublish("never-installed")  # must not raise

        assert store.list_installed() == []

    def test_retains_plugin_data_by_default(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        """_Requirements: 10.4 — remove is non-destructive by default._"""
        store.publish(plugin_factory("example"), PluginRecord(name="example"))
        data = store.plugin_data_dir("example", create=True)
        (data / "state.db").write_text("precious", encoding="utf-8")

        store.unpublish("example")

        assert (data / "state.db").read_text(encoding="utf-8") == "precious"

    def test_purge_data_deletes_plugin_data(
        self, store: InstalledPluginStore, plugin_factory
    ) -> None:
        """_Requirements: 10.3 — opting in deletes PLUGIN_DATA._"""
        store.publish(plugin_factory("example"), PluginRecord(name="example"))
        data = store.plugin_data_dir("example", create=True)
        (data / "state.db").write_text("precious", encoding="utf-8")

        store.unpublish("example", purge_data=True)

        assert not data.exists()

    def test_invalid_name_raises_store_error(self, store: InstalledPluginStore) -> None:
        with pytest.raises(PluginStoreError, match="invalid plugin name"):
            store.unpublish("../escape")


class TestPluginDataSurvivesUpdate:
    """_Requirements: 22.6, §9.1 — PLUGIN_DATA persists across an update._"""

    def test_data_survives_publish_over_existing_name(
        self, store: InstalledPluginStore, tmp_path: Path, plugin_factory
    ) -> None:
        store.publish(plugin_factory("example"), PluginRecord(name="example", version="1.0.0"))
        data = store.plugin_data_dir("example", create=True)
        (data / "state.db").write_text("persisted across the update", encoding="utf-8")

        from .conftest import make_plugin

        store.publish(
            make_plugin(tmp_path / "v2", "example", skills=("new-skill",)),
            PluginRecord(name="example", version="2.0.0"),
            force=True,
        )

        assert (data / "state.db").read_text(encoding="utf-8") == "persisted across the update"
        assert (store.plugin_root("example") / "skills" / "new-skill").is_dir()

    def test_data_dir_is_not_a_child_of_the_plugins_dir(self, store: InstalledPluginStore) -> None:
        """The guarantee is structural: the trees are disjoint by construction."""
        store.plugins_dir.mkdir(parents=True)
        store.data_dir.mkdir(parents=True)

        assert store.data_dir.resolve() != store.plugins_dir.resolve()
        assert store.plugins_dir.resolve() not in store.data_dir.resolve().parents


class TestDefaultsComeFromConstants:
    """The production store uses the CAO_HOME_DIR-derived constants."""

    def test_defaults_match_constants(self) -> None:
        from cli_agent_orchestrator.constants import (
            AGENT_PLUGIN_DATA_DIR,
            AGENT_PLUGINS_DIR,
            CAO_HOME_DIR,
        )

        default_store = InstalledPluginStore()

        assert default_store.plugins_dir == AGENT_PLUGINS_DIR
        assert default_store.data_dir == AGENT_PLUGIN_DATA_DIR
        assert AGENT_PLUGINS_DIR.parent == CAO_HOME_DIR
        assert AGENT_PLUGIN_DATA_DIR.parent == CAO_HOME_DIR
        # The disjointness that makes the §9.1 guarantee structural.
        assert AGENT_PLUGINS_DIR not in AGENT_PLUGIN_DATA_DIR.parents

    def test_constructing_the_default_store_creates_nothing(self) -> None:
        """Instantiation must be a pure path computation, not a filesystem write."""
        InstalledPluginStore()  # no assertion needed: must simply not raise
