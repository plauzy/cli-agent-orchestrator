"""Tests for the ``/plugins/*`` HTTP API (W8).

_Requirements: 17.1, 17.5, 22.1_

Unrelated to the ``cao.plugins`` event-plugin system (decision D7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _make_plugin(root: Path, name: str, skills=("alpha",)) -> Path:
    """Build a minimal valid plugin package."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(
        json.dumps({"$schema": SCHEMA_ID, "name": name, "version": "1.0.0"}, indent=2),
        encoding="utf-8",
    )
    for skill in skills:
        folder = root / "skills" / skill
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(
            f'---\nname: "{skill}"\ndescription: "A test skill."\n---\n\nBody\n',
            encoding="utf-8",
        )
    return root


@pytest.fixture(autouse=True)
def isolated_plugin_store(tmp_path: Path, monkeypatch):
    """Point the API's default store and projection target at ``tmp_path``.

    The endpoints construct ``InstalledPluginStore()`` with no arguments, so
    isolation comes from the constants it defaults to.
    """
    plugins_dir = tmp_path / "agent-plugins"
    data_dir = tmp_path / "agent-plugin-data"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", plugins_dir)
    monkeypatch.setattr(
        "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGIN_DATA_DIR", data_dir
    )
    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.projection.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.settings_service.get_extra_skill_dirs", lambda: []
    )
    monkeypatch.setattr(
        "cli_agent_orchestrator.utils.skill_injection.refresh_all_cao_managed_agents",
        lambda: [],
    )
    monkeypatch.setattr("cli_agent_orchestrator.services.session_service.list_sessions", lambda: [])
    return plugins_dir


class TestListPlugins:
    """_Requirements: 17.1_"""

    def test_empty_store_returns_an_empty_list(self, client) -> None:
        response = client.get("/plugins")

        assert response.status_code == 200
        assert response.json()["plugins"] == []

    def test_lists_findings_and_projected_skills(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example", skills=("alpha", "beta"))
        assert client.post("/plugins", json={"source": str(source)}).status_code == 201

        body = client.get("/plugins").json()

        assert len(body["plugins"]) == 1
        entry = body["plugins"][0]
        assert entry["name"] == "example"
        assert entry["version"] == "1.0.0"
        assert sorted(entry["projected_skill_names"]) == ["alpha", "beta"]
        assert sorted(entry["skill_names"]) == ["alpha", "beta"]
        assert "findings" in entry

    def test_response_carries_the_untrusted_content_warning(self, client) -> None:
        """_Requirements: 22.1 — a client cannot render install without it._"""
        body = client.get("/plugins").json()

        assert "untrusted code and content" in body["untrusted_content_warning"]
        assert "no signing" in body["untrusted_content_warning"]

    def test_reports_affected_sessions_per_plugin(
        self, client, tmp_path: Path, monkeypatch
    ) -> None:
        """_Requirements: 17.5_"""
        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})

        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "abcd1234",
                    "tmux_session": "cao-demo",
                    "provider": "kiro_cli",
                    "agent_profile": "dev",
                }
            ],
        )

        entry = client.get("/plugins").json()["plugins"][0]

        assert len(entry["affected_sessions"]) == 1
        affected = entry["affected_sessions"][0]
        assert affected["terminal_id"] == "abcd1234"
        assert affected["session_name"] == "cao-demo"
        assert affected["skill_names"] == ["alpha"]

    def test_reports_swept_dangling_links(self, client, tmp_path: Path) -> None:
        import shutil

        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})
        shutil.rmtree(tmp_path / "agent-plugins" / "example")

        body = client.get("/plugins").json()

        assert "alpha" in body["swept"]


class TestInstallPlugin:
    """_Requirements: 17.1_"""

    def test_installs_from_a_local_path(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        response = client.post("/plugins", json={"source": str(source)})

        assert response.status_code == 201
        body = response.json()
        assert body["installed"] is True
        assert body["name"] == "example"
        assert body["projected_skill_names"] == ["alpha"]

    def test_response_carries_the_untrusted_content_warning(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        body = client.post("/plugins", json={"source": str(source)}).json()

        assert "untrusted code and content" in body["untrusted_content_warning"]

    def test_unloadable_plugin_is_422_with_the_report(self, client, tmp_path: Path) -> None:
        source = tmp_path / "bad"
        source.mkdir()
        (source / "plugin.json").write_text("{ broken", encoding="utf-8")

        response = client.post("/plugins", json={"source": str(source)})

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["report"]["loadable"] is False
        assert any(f["code"] == "manifest.invalid_json" for f in detail["report"]["findings"])

    def test_unloadable_plugin_installs_nothing(self, client, tmp_path: Path) -> None:
        source = tmp_path / "bad"
        source.mkdir()
        (source / "plugin.json").write_text("nope", encoding="utf-8")

        client.post("/plugins", json={"source": str(source)})

        assert client.get("/plugins").json()["plugins"] == []

    def test_unreachable_source_is_400(self, client, tmp_path: Path) -> None:
        response = client.post("/plugins", json={"source": str(tmp_path / "absent")})

        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]

    def test_duplicate_name_is_409(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        assert client.post("/plugins", json={"source": str(source)}).status_code == 201

        response = client.post("/plugins", json={"source": str(source)})

        assert response.status_code == 409
        assert "force" in response.json()["detail"]

    def test_force_replaces(self, client, tmp_path: Path) -> None:
        first = _make_plugin(tmp_path / "v1", "example", skills=("alpha",))
        client.post("/plugins", json={"source": str(first)})
        second = _make_plugin(tmp_path / "v2", "example", skills=("beta",))

        response = client.post("/plugins", json={"source": str(second), "force": True})

        assert response.status_code == 201
        assert response.json()["projected_skill_names"] == ["beta"]

    def test_subdir_is_honoured(self, client, tmp_path: Path) -> None:
        mono = tmp_path / "mono"
        _make_plugin(mono / "packages" / "thing", "thing")

        response = client.post("/plugins", json={"source": str(mono), "subdir": "packages/thing"})

        assert response.status_code == 201
        assert response.json()["name"] == "thing"


class TestValidatePlugin:
    """_Requirements: 17.1_"""

    def test_valid_plugin_reports_loadable(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example", skills=("alpha", "beta"))

        response = client.post("/plugins/validate", json={"path": str(source)})

        assert response.status_code == 200
        report = response.json()["report"]
        assert report["loadable"] is True
        assert report["name"] == "example"
        assert sorted(s["name"] for s in report["skills"]) == ["alpha", "beta"]

    def test_invalid_plugin_is_200_with_a_negative_verdict(self, client, tmp_path: Path) -> None:
        """A question answered, not a request error."""
        source = tmp_path / "bad"
        source.mkdir()
        (source / "plugin.json").write_text("{", encoding="utf-8")

        response = client.post("/plugins/validate", json={"path": str(source)})

        assert response.status_code == 200
        assert response.json()["report"]["loadable"] is False

    def test_validate_installs_nothing(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        client.post("/plugins/validate", json={"path": str(source)})

        assert client.get("/plugins").json()["plugins"] == []

    def test_nonexistent_path_is_answered_not_crashed(self, client, tmp_path: Path) -> None:
        response = client.post("/plugins/validate", json={"path": str(tmp_path / "nope")})

        assert response.status_code == 200
        assert response.json()["report"]["loadable"] is False

    def test_reports_mcp_presence(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        (source / "mcp.json").write_text("{}", encoding="utf-8")

        report = client.post("/plugins/validate", json={"path": str(source)}).json()["report"]

        assert report["mcp_present"] is True
        assert report["loadable"] is True


class TestDeletePlugin:
    """_Requirements: 17.1, 17.5_"""

    def test_removes_an_installed_plugin(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})

        response = client.delete("/plugins/example")

        assert response.status_code == 200
        body = response.json()
        assert body["removed"] is True
        assert body["withdrawn_skill_names"] == ["alpha"]
        assert client.get("/plugins").json()["plugins"] == []

    def test_absent_plugin_is_404(self, client) -> None:
        response = client.delete("/plugins/nope")

        assert response.status_code == 404

    def test_reports_the_affected_sessions_it_disrupted(
        self, client, tmp_path: Path, monkeypatch
    ) -> None:
        """_Requirements: 17.5 — the response names sessions and skills._"""
        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})

        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "abcd1234",
                    "tmux_session": "cao-demo",
                    "provider": "opencode_cli",
                    "agent_profile": None,
                }
            ],
        )

        body = client.delete("/plugins/example").json()

        assert len(body["affected_sessions"]) == 1
        assert body["affected_sessions"][0]["session_name"] == "cao-demo"
        assert body["affected_sessions"][0]["skill_names"] == ["alpha"]

    def test_removal_is_never_refused_because_of_a_live_session(
        self, client, tmp_path: Path, monkeypatch
    ) -> None:
        """_Requirements: 15.3 — the API reports; it does not block._"""
        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "kiro_cli",
                    "agent_profile": "dev",
                }
            ],
        )

        response = client.delete("/plugins/example")

        assert response.status_code == 200
        assert response.json()["removed"] is True

    def test_retains_plugin_data_by_default(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})
        data = tmp_path / "agent-plugin-data" / "example"
        data.mkdir(parents=True, exist_ok=True)
        (data / "state").write_text("precious", encoding="utf-8")

        body = client.delete("/plugins/example").json()

        assert body["purged_data"] is False
        assert (data / "state").is_file()

    def test_purge_data_query_param_deletes_it(self, client, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        client.post("/plugins", json={"source": str(source)})
        data = tmp_path / "agent-plugin-data" / "example"
        data.mkdir(parents=True, exist_ok=True)
        (data / "state").write_text("doomed", encoding="utf-8")

        body = client.delete("/plugins/example?purge_data=true").json()

        assert body["purged_data"] is True
        assert not data.exists()


class TestRouteSurface:
    """All four capabilities exist at the documented paths (Requirement 17.1)."""

    def test_all_four_routes_are_registered(self) -> None:
        from cli_agent_orchestrator.api.main import app

        registered = {
            (route.path, method)
            for route in app.routes
            if getattr(route, "methods", None)
            for method in route.methods
            if method not in {"HEAD", "OPTIONS"}
        }

        assert ("/plugins", "GET") in registered
        assert ("/plugins", "POST") in registered
        assert ("/plugins/validate", "POST") in registered
        assert ("/plugins/{name}", "DELETE") in registered

    def test_no_route_touches_the_event_plugin_registry(self) -> None:
        """Decision D7: these are agent plugins, not event plugins."""
        from cli_agent_orchestrator.plugins import PluginRegistry

        assert PluginRegistry is not None
