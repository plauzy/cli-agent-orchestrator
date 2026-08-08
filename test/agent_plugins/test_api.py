"""HTTP API tests for the Agent Plugins endpoints.

The endpoints construct their own store from the module-level constants, so
these tests patch those symbols the way the CLI tests do — exercising the real
handler bodies rather than a re-implementation of them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

from .conftest import CANONICAL_EXAMPLE_DIR, build_plugin, write_skill


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient whose plugin store and skill store are tmp-path backed."""
    plugins_dir = tmp_path / "agent-plugins"
    data_dir = tmp_path / "agent-plugin-data"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", plugins_dir)
    monkeypatch.setattr(
        "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGIN_DATA_DIR", data_dir
    )
    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.projection.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
    monkeypatch.setattr(
        "cli_agent_orchestrator.agent_plugins.installer._refresh_agent_artifacts", lambda: None
    )

    from cli_agent_orchestrator.api.main import app

    # `base_url` is not decorative: the app's host guard rejects the
    # TestClient's default `testserver` host with a 400, so every existing API
    # test pins localhost the same way.
    test_client = TestClient(app, base_url="http://localhost")
    test_client.plugins_dir = plugins_dir  # type: ignore[attr-defined]
    test_client.skills_dir = skills_dir  # type: ignore[attr-defined]
    test_client.store = InstalledPluginStore(plugins_dir, data_dir)  # type: ignore[attr-defined]
    return test_client


class TestListPlugins:
    def test_empty_store_lists_nothing(self, client):
        response = client.get("/plugins")

        assert response.status_code == 200
        assert response.json()["plugins"] == []

    def test_the_response_states_the_untrusted_content_warning(self, client):
        """Requirement 22.1 — the API surface carries the statement too."""
        body = client.get("/plugins").json()
        assert "untrusted" in body["untrusted_content_warning"].lower()

    def test_installed_plugins_report_findings_and_projected_skills(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        client.post("/plugins", json={"source": str(source)})

        entry = client.get("/plugins").json()["plugins"][0]

        assert entry["name"] == "demo"
        assert entry["projected_skill_names"] == ["alpha"]
        assert "findings" in entry
        assert entry["affected_sessions"] == []

    def test_non_fatal_findings_are_reported(self, client, tmp_path):
        write_skill(client.skills_dir / "alpha", "alpha")
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        client.post("/plugins", json={"source": str(source)})

        entry = client.get("/plugins").json()["plugins"][0]
        assert entry["projected_skill_names"] == []
        assert entry["skill_names"] == ["alpha"]


class TestInstall:
    def test_install_from_a_local_path(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        response = client.post("/plugins", json={"source": str(source)})

        assert response.status_code == 201, response.text
        assert response.json()["installed"] is True
        assert (client.skills_dir / "alpha" / "SKILL.md").is_file()

    def test_install_the_canonical_example(self, client):
        response = client.post("/plugins", json={"source": str(CANONICAL_EXAMPLE_DIR)})

        assert response.status_code == 201
        assert response.json()["record"]["name"] == "agent-plugins-example"

    def test_an_unloadable_plugin_returns_the_full_report(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo", manifest_text="{ broken")
        response = client.post("/plugins", json={"source": str(source)})

        assert response.status_code == 422
        detail = response.json()["detail"]
        codes = [f["code"] for f in detail["report"]["findings"]]
        assert "manifest.invalid_json" in codes

    def test_an_unreachable_source_is_a_client_error(self, client, tmp_path):
        response = client.post("/plugins", json={"source": str(tmp_path / "nope")})

        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]

    def test_duplicate_install_is_refused_until_forced(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo")
        client.post("/plugins", json={"source": str(source)})

        assert client.post("/plugins", json={"source": str(source)}).status_code == 400
        forced = client.post("/plugins", json={"source": str(source), "force": True})
        assert forced.status_code == 201

    def test_the_source_kind_is_inferred_the_same_way_the_cli_infers_it(self, client, tmp_path):
        """A source that installs from the CLI must install from the panel."""
        from cli_agent_orchestrator.api.main import PluginInstallRequest, _plugin_source

        assert _plugin_source(PluginInstallRequest(source="/tmp/x")).kind == "path"
        assert _plugin_source(PluginInstallRequest(source="https://github.com/o/r")).kind == "git"

    def test_an_explicit_kind_overrides_inference(self, client):
        from cli_agent_orchestrator.api.main import PluginInstallRequest, _plugin_source

        source = _plugin_source(PluginInstallRequest(source="/tmp/x", kind="git"))
        assert source.kind == "git"


class TestValidate:
    def test_validate_reports_without_installing(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        response = client.post("/plugins/validate", json={"source": str(source)})

        assert response.status_code == 200
        assert response.json()["loadable"] is True
        assert list(client.skills_dir.iterdir()) == []

    def test_validate_of_an_unloadable_plugin_is_still_a_200_report(self, client, tmp_path):
        """Validation answers a question; an unloadable plugin is a valid answer."""
        source = build_plugin(tmp_path / "src", "demo", schema_id=None)
        response = client.post("/plugins/validate", json={"source": str(source)})

        assert response.status_code == 200
        body = response.json()
        assert body["loadable"] is False
        assert any(f["code"] == "manifest.schema_missing" for f in body["findings"])

    def test_every_finding_cites_a_clause(self, client, tmp_path):
        source = build_plugin(
            tmp_path / "src",
            "demo",
            skills=["alpha"],
            extra_manifest={"hooks": {"pre": "x"}},
            mcp_text="}{ not json",
        )
        body = client.post("/plugins/validate", json={"source": str(source)}).json()

        assert body["findings"]
        assert all(f["spec_ref"] for f in body["findings"])


class TestUninstall:
    def test_delete_removes_the_plugin(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        client.post("/plugins", json={"source": str(source)})

        response = client.request("DELETE", "/plugins/demo")

        assert response.status_code == 200
        assert response.json()["removed"] is True
        assert not (client.skills_dir / "alpha").exists()

    def test_deleting_an_absent_plugin_is_a_404(self, client):
        assert client.request("DELETE", "/plugins/ghost").status_code == 404

    def test_purge_data_is_opt_in(self, client, tmp_path):
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        client.post("/plugins", json={"source": str(source)})

        body = client.request("DELETE", "/plugins/demo?purge_data=true").json()
        assert body["purged_data"] is True
        assert not client.store.plugin_data_dir("demo").exists()

    def test_the_delete_response_reports_affected_sessions(self, client, tmp_path, monkeypatch):
        """Requirement 17.5 — reported so a client can render the warning."""
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        client.post("/plugins", json={"source": str(source)})

        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-live"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_terminals_by_session",
            lambda name: [{"id": "abcd1234", "agent_profile": "worker"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: type("P", (), {"skills": ["alpha"]})(),
        )

        body = client.request("DELETE", "/plugins/demo").json()

        assert body["affected_sessions"][0]["terminal_id"] == "abcd1234"
        assert body["affected_sessions"][0]["skill_names"] == ["alpha"]

    def test_the_list_response_reports_affected_sessions_before_any_delete(
        self, client, tmp_path, monkeypatch
    ):
        """The panel needs this *before* the DELETE, to gate on it."""
        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        client.post("/plugins", json={"source": str(source)})

        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-live"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_terminals_by_session",
            lambda name: [{"id": "abcd1234", "agent_profile": "worker"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: type("P", (), {"skills": ["alpha"]})(),
        )

        entry = client.get("/plugins").json()["plugins"][0]
        assert entry["affected_sessions"][0]["session_name"] == "cao-live"


class TestRoutesRegistered:
    def test_all_four_endpoints_exist(self):
        from cli_agent_orchestrator.api.main import app

        paths = {(r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r, "methods")}
        assert ("/plugins", ("GET",)) in paths
        assert ("/plugins", ("POST",)) in paths
        assert ("/plugins/validate", ("POST",)) in paths
        assert ("/plugins/{name}", ("DELETE",)) in paths
