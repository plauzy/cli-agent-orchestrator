"""Unit tests for the plugin source resolver (W4).

_Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

The git tests build **local** repositories with ``git init`` rather than
reaching the network: the resolver's contract is about what it asks git to do,
not about GitHub's availability, and a network-dependent unit test would be a
flake generator.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins.models import PluginSource
from cli_agent_orchestrator.agent_plugins.resolver import (
    PluginResolutionError,
    ResolvedSource,
    detect_source,
    resolve,
)

from .conftest import make_plugin


def _git(*args: str, cwd: Path) -> str:
    """Run git in a test fixture repo with deterministic identity."""
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A local git repo whose root is a valid plugin package."""
    repo = tmp_path / "origin-repo"
    make_plugin(repo, "example", skills=("example-skill",))
    _git("init", "--quiet", "--initial-branch=main", cwd=repo)
    _git("add", ".", cwd=repo)
    _git("commit", "--quiet", "-m", "initial", cwd=repo)
    return repo


@pytest.fixture
def git_monorepo(tmp_path: Path) -> Path:
    """A local git repo with the plugin in a nested subdirectory."""
    repo = tmp_path / "monorepo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "README.md").write_text("not a plugin", encoding="utf-8")
    make_plugin(repo / "agent-plugin" / "cao", "cao", skills=("cao-session-management",))
    _git("init", "--quiet", "--initial-branch=main", cwd=repo)
    _git("add", ".", cwd=repo)
    _git("commit", "--quiet", "-m", "initial", cwd=repo)
    return repo


class TestPathSource:
    """_Requirements: 8.1 — a local directory is copied, never referenced._"""

    def test_copies_contents_into_staging(self, tmp_path: Path, plugin_factory) -> None:
        origin = plugin_factory("example", skills=("alpha", "beta"))
        staging = tmp_path / "staging"

        resolved = resolve(PluginSource(kind="path", location=str(origin)), staging)

        assert resolved.root == staging.resolve()
        assert (staging / "plugin.json").is_file()
        assert (staging / "skills" / "alpha" / "SKILL.md").is_file()
        assert (staging / "skills" / "beta" / "SKILL.md").is_file()

    def test_staging_is_independent_of_the_original(self, tmp_path: Path, plugin_factory) -> None:
        """The whole point of copying: the source cannot change under us."""
        origin = plugin_factory("example")
        staging = tmp_path / "staging"
        resolve(PluginSource(kind="path", location=str(origin)), staging)

        (origin / "plugin.json").write_text("mutated after resolve", encoding="utf-8")

        assert "mutated" not in (staging / "plugin.json").read_text(encoding="utf-8")

    def test_does_not_mutate_the_original(self, tmp_path: Path, plugin_factory) -> None:
        origin = plugin_factory("example")
        before = sorted(path.name for path in origin.rglob("*"))

        resolve(PluginSource(kind="path", location=str(origin)), tmp_path / "staging")

        assert sorted(path.name for path in origin.rglob("*")) == before

    def test_records_no_resolved_ref(self, tmp_path: Path, plugin_factory) -> None:
        resolved = resolve(
            PluginSource(kind="path", location=str(plugin_factory("example"))),
            tmp_path / "staging",
        )

        assert resolved.resolved_ref is None

    def test_expands_user_home(self, tmp_path: Path, monkeypatch, plugin_factory) -> None:
        origin = plugin_factory("example")
        monkeypatch.setenv("HOME", str(origin.parent))

        resolved = resolve(
            PluginSource(kind="path", location=f"~/{origin.name}"), tmp_path / "staging"
        )

        assert (resolved.root / "plugin.json").is_file()

    def test_preserves_internal_symlinks(self, tmp_path: Path, plugin_factory) -> None:
        origin = plugin_factory("example")
        (origin / "skills" / "linked").symlink_to("example-skill")

        resolve(PluginSource(kind="path", location=str(origin)), tmp_path / "staging")

        assert (tmp_path / "staging" / "skills" / "linked").is_symlink()

    def test_preserves_an_escaping_symlink_as_a_symlink(
        self, tmp_path: Path, plugin_factory
    ) -> None:
        """Dereferencing here would smuggle outside content past containment.

        The escaping link must arrive in staging still a link, so the
        validator's containment check is the thing that rejects it.
        """
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret", encoding="utf-8")
        origin = plugin_factory("example")
        (origin / "escape").symlink_to(outside, target_is_directory=True)

        resolve(PluginSource(kind="path", location=str(origin)), tmp_path / "staging")

        assert (tmp_path / "staging" / "escape").is_symlink()


class TestPathSourceErrors:
    """_Requirements: 8.4 — report the cause, change nothing._"""

    def test_missing_path_is_reported(self, tmp_path: Path) -> None:
        with pytest.raises(PluginResolutionError, match="does not exist"):
            resolve(
                PluginSource(kind="path", location=str(tmp_path / "absent")),
                tmp_path / "staging",
            )

    def test_file_instead_of_directory_is_reported(self, tmp_path: Path) -> None:
        target = tmp_path / "plugin.zip"
        target.write_text("not a directory", encoding="utf-8")

        with pytest.raises(PluginResolutionError, match="not a directory"):
            resolve(PluginSource(kind="path", location=str(target)), tmp_path / "staging")

    def test_error_message_names_the_offending_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope-here"

        with pytest.raises(PluginResolutionError) as caught:
            resolve(PluginSource(kind="path", location=str(missing)), tmp_path / "staging")

        assert str(missing) in str(caught.value)


class TestGitSource:
    """_Requirements: 8.2 — clone and record the resolved commit._"""

    def test_clones_into_staging(self, tmp_path: Path, git_repo: Path) -> None:
        staging = tmp_path / "staging"

        resolved = resolve(PluginSource(kind="git", location=str(git_repo)), staging)

        assert (resolved.root / "plugin.json").is_file()
        assert (resolved.root / "skills" / "example-skill" / "SKILL.md").is_file()

    def test_records_the_resolved_commit(self, tmp_path: Path, git_repo: Path) -> None:
        expected = _git("rev-parse", "HEAD", cwd=git_repo)

        resolved = resolve(PluginSource(kind="git", location=str(git_repo)), tmp_path / "staging")

        assert resolved.resolved_ref == expected
        assert len(resolved.resolved_ref or "") == 40

    def test_clone_requests_a_shallow_non_recursive_clone(
        self, tmp_path: Path, git_repo: Path, monkeypatch
    ) -> None:
        """Assert the flags, not the resulting history depth.

        ``git clone`` silently ignores ``--depth`` when the source is a local
        path, so inspecting the clone's history would test git's local-clone
        optimization rather than the resolver's contract.
        """
        from cli_agent_orchestrator.agent_plugins import resolver as resolver_module

        recorded: list[list[str]] = []
        original = resolver_module._run_git

        def _spy(args, cwd=None):
            recorded.append(list(args))
            return original(args, cwd=cwd)

        monkeypatch.setattr(resolver_module, "_run_git", _spy)

        resolve(PluginSource(kind="git", location=str(git_repo)), tmp_path / "staging")

        clone_args = next(args for args in recorded if args and args[0] == "clone")
        assert "--depth" in clone_args
        assert clone_args[clone_args.index("--depth") + 1] == "1"
        assert "--no-recurse-submodules" in clone_args

    def test_git_metadata_is_not_left_in_the_plugin_root(
        self, tmp_path: Path, git_repo: Path
    ) -> None:
        """PLUGIN_ROOT holds package bytes, not repository history."""
        resolved = resolve(PluginSource(kind="git", location=str(git_repo)), tmp_path / "staging")

        assert not (resolved.staging / ".git").exists()
        assert not (resolved.root / ".git").exists()
        # The package itself survived the cleanup.
        assert (resolved.root / "plugin.json").is_file()

    def test_clones_a_tag_ref(self, tmp_path: Path, git_repo: Path) -> None:
        _git("tag", "v1.0.0", cwd=git_repo)
        tagged = _git("rev-parse", "HEAD", cwd=git_repo)
        _git("commit", "--quiet", "--allow-empty", "-m", "after the tag", cwd=git_repo)

        resolved = resolve(
            PluginSource(kind="git", location=str(git_repo), ref="v1.0.0"),
            tmp_path / "staging",
        )

        assert resolved.resolved_ref == tagged

    def test_clones_a_branch_ref(self, tmp_path: Path, git_repo: Path) -> None:
        _git("checkout", "--quiet", "-b", "feature", cwd=git_repo)
        (git_repo / "marker.txt").write_text("on the branch", encoding="utf-8")
        _git("add", ".", cwd=git_repo)
        _git("commit", "--quiet", "-m", "branch work", cwd=git_repo)
        expected = _git("rev-parse", "HEAD", cwd=git_repo)

        resolved = resolve(
            PluginSource(kind="git", location=str(git_repo), ref="feature"),
            tmp_path / "staging",
        )

        assert resolved.resolved_ref == expected
        assert (resolved.root / "marker.txt").is_file()

    def test_clones_a_full_commit_id_via_fallback(self, tmp_path: Path, git_repo: Path) -> None:
        """``clone --branch`` cannot take a commit id; the fallback can.

        This is the path that replays an install record, whose recorded ref is
        always a commit id.
        """
        first = _git("rev-parse", "HEAD", cwd=git_repo)
        (git_repo / "later.txt").write_text("later", encoding="utf-8")
        _git("add", ".", cwd=git_repo)
        _git("commit", "--quiet", "-m", "later", cwd=git_repo)
        # Fetch-by-object-id must be permitted by the serving repo.
        _git("config", "uploadpack.allowReachableSHA1InWant", "true", cwd=git_repo)
        _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=git_repo)

        resolved = resolve(
            PluginSource(kind="git", location=str(git_repo), ref=first),
            tmp_path / "staging",
        )

        assert resolved.resolved_ref == first
        assert not (resolved.root / "later.txt").exists()


class TestGitSubdir:
    """_Requirements: 8.3 — a subdirectory is the candidate plugin root._"""

    def test_addresses_a_nested_subdirectory(self, tmp_path: Path, git_monorepo: Path) -> None:
        resolved = resolve(
            PluginSource(kind="git", location=str(git_monorepo), subdir="agent-plugin/cao"),
            tmp_path / "staging",
        )

        assert resolved.root == (tmp_path / "staging" / "agent-plugin" / "cao").resolve()
        assert (resolved.root / "plugin.json").is_file()

    def test_root_is_the_subdir_not_the_repo_root(self, tmp_path: Path, git_monorepo: Path) -> None:
        resolved = resolve(
            PluginSource(kind="git", location=str(git_monorepo), subdir="agent-plugin/cao"),
            tmp_path / "staging",
        )

        assert not (resolved.root / "docs").exists()
        assert resolved.staging != resolved.root

    def test_subdir_works_for_a_path_source_too(self, tmp_path: Path) -> None:
        origin = tmp_path / "mono"
        make_plugin(origin / "packages" / "thing", "thing")

        resolved = resolve(
            PluginSource(kind="path", location=str(origin), subdir="packages/thing"),
            tmp_path / "staging",
        )

        assert (resolved.root / "plugin.json").is_file()

    @pytest.mark.parametrize("subdir", ["", ".", "./", "//"])
    def test_empty_subdir_means_the_staging_root(
        self, tmp_path: Path, subdir: str, plugin_factory
    ) -> None:
        staging = tmp_path / "staging"

        resolved = resolve(
            PluginSource(kind="path", location=str(plugin_factory("example")), subdir=subdir),
            staging,
        )

        assert resolved.root == staging.resolve()

    def test_normalizes_redundant_separators(self, tmp_path: Path) -> None:
        origin = tmp_path / "mono"
        make_plugin(origin / "packages" / "thing", "thing")

        resolved = resolve(
            PluginSource(kind="path", location=str(origin), subdir="packages//./thing"),
            tmp_path / "staging",
        )

        assert resolved.root == (tmp_path / "staging" / "packages" / "thing").resolve()

    @pytest.mark.parametrize("subdir", ["../escape", "packages/../../escape", "/etc"])
    def test_escaping_subdir_is_refused(self, tmp_path: Path, subdir: str, plugin_factory) -> None:
        """Containment is enforced here; the validator starts *at* a root."""
        with pytest.raises(PluginResolutionError):
            resolve(
                PluginSource(kind="path", location=str(plugin_factory("example")), subdir=subdir),
                tmp_path / "staging",
            )

    def test_nonexistent_subdir_is_reported(self, tmp_path: Path, plugin_factory) -> None:
        with pytest.raises(PluginResolutionError, match="not a directory"):
            resolve(
                PluginSource(
                    kind="path", location=str(plugin_factory("example")), subdir="no/such/dir"
                ),
                tmp_path / "staging",
            )

    def test_subdir_symlink_escaping_the_source_is_refused(
        self, tmp_path: Path, plugin_factory
    ) -> None:
        """Realpath containment, not lexical: a link out is still an escape."""
        outside = tmp_path / "outside"
        make_plugin(outside, "outside")
        origin = plugin_factory("example")
        (origin / "link").symlink_to(outside, target_is_directory=True)

        with pytest.raises(PluginResolutionError):
            resolve(
                PluginSource(kind="path", location=str(origin), subdir="link"),
                tmp_path / "staging",
            )


class TestGitSourceErrors:
    """_Requirements: 8.4 — a failed git operation is reported with its cause._"""

    def test_unreachable_repository_is_reported(self, tmp_path: Path) -> None:
        with pytest.raises(PluginResolutionError, match="could not clone"):
            resolve(
                PluginSource(kind="git", location=str(tmp_path / "not-a-repo")),
                tmp_path / "staging",
            )

    def test_missing_ref_is_reported(self, tmp_path: Path, git_repo: Path) -> None:
        with pytest.raises(PluginResolutionError) as caught:
            resolve(
                PluginSource(kind="git", location=str(git_repo), ref="no-such-branch"),
                tmp_path / "staging",
            )

        assert "no-such-branch" in str(caught.value)

    def test_failure_leaves_nothing_outside_staging(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        sibling = tmp_path / "sibling"
        sibling.mkdir()

        with pytest.raises(PluginResolutionError):
            resolve(PluginSource(kind="git", location=str(tmp_path / "nope")), staging)

        assert list(sibling.iterdir()) == []

    def test_unknown_source_kind_is_reported(self, tmp_path: Path) -> None:
        with pytest.raises(PluginResolutionError, match="unsupported plugin source kind"):
            resolve(PluginSource(kind="oci", location="registry.test/x"), tmp_path / "staging")


class TestSubmodulesAreNotInitialized:
    """A stated non-behavior, enforced by flags rather than assumed.

    An ambient ``submodule.recurse=true`` would otherwise make ``git clone``
    recurse, pulling third-party content into staging.
    """

    @pytest.fixture
    def repo_with_submodule(self, tmp_path: Path, git_repo: Path) -> Path:
        inner = tmp_path / "inner"
        inner.mkdir()
        (inner / "inner.txt").write_text("submodule content", encoding="utf-8")
        _git("init", "--quiet", "--initial-branch=main", cwd=inner)
        _git("add", ".", cwd=inner)
        _git("commit", "--quiet", "-m", "inner", cwd=inner)

        _git(
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "--quiet",
            str(inner),
            "vendor/inner",
            cwd=git_repo,
        )
        _git("commit", "--quiet", "-m", "add submodule", cwd=git_repo)
        return git_repo

    def test_submodule_content_is_not_fetched(
        self, tmp_path: Path, repo_with_submodule: Path
    ) -> None:
        resolved = resolve(
            PluginSource(kind="git", location=str(repo_with_submodule)),
            tmp_path / "staging",
        )

        assert not (resolved.root / "vendor" / "inner" / "inner.txt").exists()

    def test_submodule_content_is_not_fetched_despite_ambient_recurse_config(
        self, tmp_path: Path, repo_with_submodule: Path, monkeypatch
    ) -> None:
        """The flags must beat a user's global ``submodule.recurse=true``."""
        home = tmp_path / "fake-home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            '[submodule]\n\trecurse = true\n[protocol "file"]\n\tallow = always\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        resolved = resolve(
            PluginSource(kind="git", location=str(repo_with_submodule)),
            tmp_path / "staging",
        )

        assert not (resolved.root / "vendor" / "inner" / "inner.txt").exists()


class TestNoIndexOrSignatureBehavior:
    """_Requirements: 8.5 — no index lookup, no solving, no signature check._"""

    def test_a_bare_name_is_treated_as_a_local_path_not_an_index_lookup(
        self, tmp_path: Path
    ) -> None:
        """There is no registry, so a bare name is just a (missing) directory."""
        source = detect_source("some-plugin-name")

        assert source.kind == "path"
        with pytest.raises(PluginResolutionError, match="does not exist"):
            resolve(source, tmp_path / "staging")

    def test_resolved_source_exposes_no_verification_fields(self) -> None:
        assert set(ResolvedSource.__dataclass_fields__) == {
            "root",
            "staging",
            "source",
            "resolved_ref",
        }


class TestDetectSource:
    @pytest.mark.parametrize(
        "location",
        [
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "http://example.test/repo.git",
            "git://example.test/repo",
            "ssh://git@example.test/owner/repo.git",
            "git@github.com:owner/repo.git",
        ],
    )
    def test_remote_locations_are_git(self, location: str) -> None:
        assert detect_source(location).kind == "git"

    @pytest.mark.parametrize("location", ["/abs/path", "./rel/path", "rel/path", "."])
    def test_local_locations_are_path(self, location: str) -> None:
        assert detect_source(location).kind == "path"

    def test_carries_ref_and_subdir_through(self) -> None:
        source = detect_source(
            "https://github.com/owner/repo", ref="v1.2.3", subdir="agent-plugin/cao"
        )

        assert source.ref == "v1.2.3"
        assert source.subdir == "agent-plugin/cao"

    def test_strips_surrounding_whitespace(self) -> None:
        assert detect_source("  /abs/path  ").location == "/abs/path"
