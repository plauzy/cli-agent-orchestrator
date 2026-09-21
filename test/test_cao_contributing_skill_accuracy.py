"""The ``cao-contributing`` skill documents CI. This pins it to the real CI.

A skill that describes the CI gate map in prose drifts the moment a job is
renamed, added, or has its command changed -- and a stale skill is worse than no
skill, because an agent will act on it confidently. That is not hypothetical:
review on #448 caught three factual drifts (a wrong ``--cov`` target, a moved
recorder path, and a gate map missing six jobs) that accumulated in the 46 days
the PR sat open.

These tests read ``.github/workflows/ci.yml`` and fail if the skill no longer
matches it, so the next rename is caught by CI rather than by a reviewer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SKILL = REPO_ROOT / "skills" / "cao-contributing" / "SKILL.md"
PACKAGED_SKILL = (
    REPO_ROOT / "src" / "cli_agent_orchestrator" / "skills" / "cao-contributing" / "SKILL.md"
)

# Jobs deliberately left out of the skill's gate map, with the reason. Anything
# not listed here MUST appear in the map -- that is what makes the test a gate
# rather than a suggestion.
INTENTIONALLY_UNDOCUMENTED: dict[str, str] = {
    "Dependency Review": "advisory-only, PR-scoped; no local equivalent to run",
}

# Shipped skills whose names do not start with ``cao-``. The reference matcher
# below is anchored to the ``cao-`` prefix plus this allowlist rather than to
# ``**bold**`` generally, because the gate-map table is full of bold prose
# (``**Yes**``) that would otherwise be read as skill names.
NON_CAO_SKILL_NAMES = frozenset({"agui-author", "mcp-apps-builder"})

# Floor for the reference guard below. A pattern that stops matching would make
# the existence check vacuous instead of failing, so the count is asserted
# separately. Review on #448 flagged exactly this hazard in the ``examples/``
# parametrize, which collects zero tests if its findall returns nothing.
MINIMUM_SKILL_REFERENCES = 3


def _ci_job_names() -> set[str]:
    spec = yaml.safe_load(CI_WORKFLOW.read_text())
    names: set[str] = set()
    for job_id, job in (spec.get("jobs") or {}).items():
        name = (job or {}).get("name") or job_id
        # Strip matrix interpolation: "Rust TUI (${{ matrix.label }})" -> "Rust TUI"
        name = re.sub(r"\s*\(\$\{\{.*?\}\}\)", "", name).strip()
        names.add(name)
    return names


def _real_skill_names() -> set[str]:
    """Directories under ``skills/`` that actually contain a ``SKILL.md``.

    Mirrors the Agent Plugins discovery rule: one skill per immediate child
    directory holding a ``SKILL.md``, no deeper recursion.
    """
    skills_dir = REPO_ROOT / "skills"
    return {p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()}


def _referenced_skill_names() -> set[str]:
    """Skill names the skill text points at, in bold or backticks.

    Anchored to the ``cao-`` prefix plus ``NON_CAO_SKILL_NAMES``. A looser
    matcher over ``**...**`` would capture gate-map prose and fail spuriously;
    the cost of this precision is that a future non-``cao-`` skill must be added
    to the allowlist, which is a visible maintenance point rather than a silent
    miss.
    """
    text = _skill_text()
    found = set(re.findall(r"\*\*(cao-[a-z0-9-]+)\*\*|`(cao-[a-z0-9-]+)`", text))
    names = {m for pair in found for m in pair if m}
    for extra in NON_CAO_SKILL_NAMES:
        if re.search(rf"\*\*{re.escape(extra)}\*\*|`{re.escape(extra)}`", text):
            names.add(extra)
    # The skill documents itself; that is not a route to verify.
    return names - {"cao-contributing"}


def _skill_text() -> str:
    return SKILL.read_text()


class TestTheGateMapMatchesCi:
    def test_every_ci_job_is_documented(self):
        documented = _skill_text()
        missing = sorted(
            name
            for name in _ci_job_names()
            if name not in INTENTIONALLY_UNDOCUMENTED and name not in documented
        )
        assert not missing, (
            "These CI jobs are not mentioned in the cao-contributing gate map: "
            f"{missing}. Add them to the table in {SKILL.relative_to(REPO_ROOT)}, or "
            "record why they are omitted in INTENTIONALLY_UNDOCUMENTED."
        )

    def test_no_phantom_jobs_are_documented(self):
        """The skill must not promise a job that CI does not run."""
        real = _ci_job_names()
        # Only the FIRST column of a table row names a job -- later columns hold
        # the blocking verdict, which is also bolded.
        claimed = {
            m.strip() for m in re.findall(r"^\|\s*\*\*(.+?)\*\*", _skill_text(), re.MULTILINE)
        }
        phantom = sorted(
            c for c in claimed if not any(c.startswith(r) or r.startswith(c) for r in real)
        )
        assert not phantom, f"The skill documents jobs that no longer exist in ci.yml: {phantom}"


class TestReferencedSkillsExist:
    """A skill that routes agents elsewhere must not name a skill that is absent.

    #448 shipped a route to ``cao-skill-creator``, which never existed in
    ``skills/``. A dangling route is worse in a packaged skill than in ordinary
    prose: the frontmatter ``description`` is the text an agent matches on when
    deciding whether to load the skill, so a phantom name both fails to route
    and widens the activation surface.
    """

    def test_the_reference_guard_has_something_to_check(self):
        found = _referenced_skill_names()
        assert len(found) >= MINIMUM_SKILL_REFERENCES, (
            f"Expected at least {MINIMUM_SKILL_REFERENCES} skill references in "
            f"{SKILL.relative_to(REPO_ROOT)}, found {sorted(found)}. If the routing "
            "section was reworded, lower this floor deliberately -- do not let the "
            "existence check below silently verify nothing."
        )

    def test_every_referenced_skill_exists(self):
        missing = sorted(_referenced_skill_names() - _real_skill_names())
        assert not missing, (
            f"{SKILL.relative_to(REPO_ROOT)} references skills that do not exist: "
            f"{missing}. Real skills: {sorted(_real_skill_names())}. Either point the "
            "reference at a skill that exists, drop it, or add the skill."
        )


class TestQuotedCommandsAreReal:
    def test_the_coverage_target_matches_ci(self):
        ci = CI_WORKFLOW.read_text()
        match = re.search(r"--cov=(\S+)", ci)
        assert match, "ci.yml no longer passes --cov; update this test."
        target = match.group(1)
        # Compare exact tokens. A substring check would pass "--cov=src" against a
        # skill saying "--cov=src/cli_agent_orchestrator", which is the very drift
        # this test exists to catch.
        quoted = set(re.findall(r"--cov=([^\s`|)]+)", _skill_text()))
        assert target in quoted, (
            f"ci.yml runs coverage as --cov={target}, but the skill quotes {quoted or '{}'}. "
            "A wrong coverage target sends contributors looking at the wrong report."
        )

    def test_the_marker_expression_matches_ci(self):
        ci = CI_WORKFLOW.read_text()
        match = re.search(r'-m\s+"([^"]+)"', ci)
        assert match, "ci.yml no longer passes -m; update this test."
        assert match.group(1) in _skill_text(), (
            f'ci.yml deselects with -m "{match.group(1)}"; the skill must quote it '
            "verbatim, because it overrides any local addopts."
        )


class TestReferencedPathsExist:
    @pytest.mark.parametrize("quoted", re.findall(r"`(examples/[^`]+?)`", SKILL.read_text()))
    def test_every_referenced_example_path_exists(self, quoted: str):
        path = REPO_ROOT / quoted.rstrip("/")
        assert path.exists(), (
            f"The skill references {quoted}, which does not exist. "
            "Paths in a skill are instructions an agent will follow literally."
        )


class TestMypyToleranceClaim:
    def test_mypy_is_still_non_blocking(self):
        """The skill tells contributors not to 'fix' red mypy. Verify that holds."""
        spec = yaml.safe_load(CI_WORKFLOW.read_text())
        steps = spec["jobs"]["lint"]["steps"]
        mypy_steps = [s for s in steps if "mypy" in str(s.get("run", ""))]
        assert mypy_steps, "The lint job no longer runs mypy; update the skill."
        assert all(s.get("continue-on-error") is True for s in mypy_steps), (
            "mypy is now BLOCKING in CI. The skill's guidance to ignore pre-existing "
            "mypy errors is actively harmful until it is rewritten."
        )


class TestPackagedMirrorStaysInLockstep:
    def test_the_two_copies_are_identical(self):
        assert PACKAGED_SKILL.read_text() == SKILL.read_text(), (
            "skills/ and the packaged mirror have diverged. "
            "Run `uv run python scripts/sync_skills.py`."
        )
