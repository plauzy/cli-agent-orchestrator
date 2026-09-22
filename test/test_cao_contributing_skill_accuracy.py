"""The ``cao-contributing`` skill documents CI. This pins it to the real CI.

A skill that describes the CI gate map in prose drifts the moment a job is
renamed, added, or has its command changed -- and a stale skill is worse than no
skill, because an agent will act on it confidently. That is not hypothetical:
review on #448 caught three factual drifts (a wrong ``--cov`` target, a moved
recorder path, and a gate map that named only six of the thirteen ``ci.yml`` jobs
it is required to cover) that accumulated in the 46 days the PR sat open.

The size of that last gap was reported three different ways -- "six", "five", and
"four newly documented jobs plus one non-job step row" -- and all three are real
measurements of different things, which is why the derivation is written down
rather than the number alone. Re-derive it from the gate map at the commit that
introduced it (``ec433f38``) against ``_ci_job_names()``, using this test's own
"documented" test, namely that the job name appears anywhere in the skill:

* **Seven** of the thirteen jobs were absent. The six named were Unit Tests, Code
  Quality, AG-UI demo, CAO MCP Apps, Web UI Build -- all five as table rows --
  plus Security Scan, which appeared only in prose.
* ``95a08178`` closed **five** of the seven. It added six job rows, but one of
  them, Security Scan, was already named, so the newly-documented count is five
  where the new-row count is six (seven counting the ``step:`` row, which
  describes a step inside an already-listed job rather than a job of its own).
  Discounting Security Scan and treating the split ``CAO MCP Apps E2E`` row as a
  restatement of an existing one gives the **four** reported elsewhere.
* ``1d35d872`` closed the sixth, Agent Plugins dog-food.
* The seventh was ``Dependency Review``, which this file had wrongly *exempted*
  rather than documented (see ``INTENTIONALLY_UNDOCUMENTED``). With the exemption
  removed and the row added, every ``ci.yml`` job is documented and no exemption
  remains -- so the count that matters now is zero, and it is enforced rather
  than asserted in a docstring.

These tests read ``.github/workflows/ci.yml`` and fail if the skill no longer
matches it, so the next rename is caught by CI rather than by a reviewer. Three
properties are asserted here that prose review kept missing:

* Every gate-map row's **Blocking?** verdict, against that job's real job-level
  ``continue-on-error``. Before this, the column was decorative -- only that a
  job *name* appeared somewhere in the file was checked, so a job flipping
  blocking/tolerated passed silently.
* A non-vacuity floor under every matcher whose result feeds a ``parametrize``.
  Those run at collection time, so a matcher that stops matching collects zero
  tests and reports success instead of failing.
* That the isolated-``HOME`` recipe actually isolates, and actually reports the
  test's exit status. It is the one snippet whose output a reader treats as
  evidence, so a recipe that lies is worse than none.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SKILL = REPO_ROOT / "skills" / "cao-contributing" / "SKILL.md"

# Jobs deliberately left out of the skill's gate map, with the reason. Anything
# not listed here MUST appear in the map -- that is what makes the test a gate
# rather than a suggestion.
#
# Deliberately EMPTY, and that is the point: the one entry this ever held --
# ``Dependency Review``, exempted as "advisory-only, PR-scoped; no local
# equivalent to run" -- was simply false about ci.yml. ``jobs.dependency-review``
# carries no job-level or step-level ``continue-on-error`` and is configured with
# ``fail-on-severity: high`` plus ``deny-licenses``, so it fails the PR on a
# qualifying finding. An exemption is a hole in the gate by construction, so the
# bar for adding one is "ci.yml genuinely does not gate on it", not "there is
# nothing to run locally". Having no local equivalent is a reason to DOCUMENT a
# job, not to hide it.
INTENTIONALLY_UNDOCUMENTED: dict[str, str] = {}

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

# The ``examples/`` path matcher is a SECOND, independent parametrize site with
# the same collection-time hazard, and ``MINIMUM_SKILL_REFERENCES`` does not
# cover it -- that floor guards the skill-name matcher. This one is its own.
EXAMPLE_PATH_PATTERN = r"`(examples/[^`]+?)`"
MINIMUM_EXAMPLE_PATH_REFERENCES = 3

# The Unit Tests job narrows its own selection with these BEFORE ``-m`` is
# applied, so ``-m "not e2e"`` alone does not describe what CI runs: the Kiro
# provider integration test is excluded by path and never executes in CI. The
# skill has to say so, and this pins that correction against silent reversion.
CI_REQUIRED_IGNORES = (
    "--ignore=test/providers/test_kiro_cli_integration.py",
    "--ignore=test/e2e",
)


def _ci_spec() -> dict:
    spec = yaml.safe_load(CI_WORKFLOW.read_text())
    assert isinstance(spec, dict), f"{CI_WORKFLOW} did not parse as a YAML mapping."
    return spec


def _canonical_job_name(name: str) -> str:
    """Strip matrix interpolation only: ``Rust TUI (${{ matrix.label }})`` -> ``Rust TUI``.

    Deliberately does NOT strip ordinary parentheticals. ``(Playwright)`` and
    ``(AC3)`` are part of the real check name a contributor reads on the PR, so
    dropping them would make ``CAO MCP Apps E2E`` compare equal to
    ``CAO MCP Apps E2E (Playwright)`` -- one of the two truncations the exact
    membership test below exists to reject.
    """
    return re.sub(r"\s*\(\$\{\{.*?\}\}\)", "", name).strip()


def _ci_jobs_by_name() -> dict[str, dict]:
    """Canonical job name -> the job's parsed mapping."""
    jobs: dict[str, dict] = {}
    for job_id, job in (_ci_spec().get("jobs") or {}).items():
        job = job or {}
        jobs[_canonical_job_name(job.get("name") or job_id)] = job
    return jobs


def _ci_job_names() -> set[str]:
    return set(_ci_jobs_by_name())


def _truthy_continue_on_error(value: object) -> bool:
    """Whether a ``continue-on-error`` value tolerates failure.

    Accepts the quoted string form as well as the bool, because both are legal
    YAML for this key and a reader scanning for ``true`` should not be fooled by
    quoting.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().strip("'\"").lower() == "true"
    return False


def _job_is_blocking(job: dict) -> bool:
    """Whether this job's failure fails the workflow.

    ``continue-on-error`` is absent on every job in ``ci.yml`` today, and absent
    means BLOCKING -- GitHub defaults the key to false. That default is the whole
    reason this has to be derived rather than read: the tolerated branch is
    currently unreachable from ``ci.yml``, so ``TestTheBlockingDerivationItself``
    pins it directly instead of trusting that it works.

    STEP-level ``continue-on-error`` is deliberately not consulted. It tolerates
    one step, not the job, and ``ci.yml`` carries four of them -- the mypy step
    plus three artifact uploads -- while all four of those jobs remain hard
    gates. Folding steps in here would mis-report three blocking jobs as
    tolerated.
    """
    return not _truthy_continue_on_error(job.get("continue-on-error"))


def _skill_text() -> str:
    return SKILL.read_text()


def _gate_map_rows() -> list[tuple[str, str, str]]:
    """Three-cell Markdown table rows from the skill, cells stripped."""
    rows: list[tuple[str, str, str]] = []
    for line in _skill_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 3:
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def _gate_map_job_rows() -> dict[str, str]:
    """Canonical job name -> the raw text of that row's ``Blocking?`` cell.

    Header, separator, and ``step:`` continuation rows are skipped: a step row
    describes a step inside an already-listed job, not a job of its own.
    """
    rows: dict[str, str] = {}
    for first, _runs, verdict in _gate_map_rows():
        if first == "Job" or set(first) <= set("-: "):
            continue
        bold = re.match(r"\*\*(.+?)\*\*", first)
        if not bold:  # e.g. the "step:" continuation row, whose bold is not leading
            continue
        rows[_canonical_job_name(bold.group(1))] = verdict
    return rows


def _claimed_blocking(verdict_cell: str) -> bool | None:
    """The JOB-level verdict a ``Blocking?`` cell claims, or None if unreadable.

    The FIRST verdict token wins, because a cell may carry the job verdict plus a
    step-level caveat: Code Quality reads ``black/isort **yes**; **mypy is
    non-blocking**`` and the job is blocking. Returning None rather than guessing
    keeps an unreadable cell a test failure instead of a silent pass.
    """
    for match in re.finditer(r"non-blocking|\*\*(yes|no)\*\*", verdict_cell, re.IGNORECASE):
        if match.group(0).lower() == "non-blocking":
            return False
        return match.group(1).lower() == "yes"
    return None


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


def _referenced_example_paths() -> list[str]:
    return re.findall(EXAMPLE_PATH_PATTERN, _skill_text())


def _isolated_home_recipe() -> str:
    """The fenced ``bash`` block that runs a test under a throwaway ``HOME``.

    Located by its ``mktemp -d``, and asserted unique: if a second isolation
    recipe is ever added, the guards below would silently check only one of
    them, which is the same vacuity hazard the parametrize floors exist for.
    """
    blocks = re.findall(r"```bash\n(.*?)```", _skill_text(), re.DOTALL)
    matching = [b for b in blocks if "mktemp -d" in b]
    assert len(matching) == 1, (
        f"Expected exactly one mktemp-based isolation recipe, found {len(matching)}. "
        "Update this helper deliberately rather than checking an arbitrary one."
    )
    return matching[0]


def _unit_tests_pytest_command() -> str:
    """The Unit Tests job's pytest invocation, and only that one.

    Anchored to ``jobs.test`` rather than regexed out of the whole file because
    ``ci.yml`` runs a SECOND pytest, with its own ``--cov`` and ``-m``, in the
    ``cao-mcp-apps`` job (the coverage-ratchet floor). A whole-file regex can
    therefore validate the wrong job: verified by deleting ``--cov`` and ``-m``
    from the Unit Tests step, which left the previous unanchored assertions green
    while the documented job produced no coverage and deselected nothing.
    """
    steps = _ci_spec()["jobs"]["test"]["steps"]
    commands = [str(s.get("run", "")) for s in steps if "pytest" in str(s.get("run", ""))]
    assert len(commands) == 1, (
        "Expected exactly one pytest step in the Unit Tests job, found "
        f"{len(commands)}. Update this helper deliberately -- picking one of "
        "several silently would reintroduce the ambiguity it exists to remove."
    )
    return commands[0]


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
        """The skill must not promise a job that CI does not run.

        Exact set membership, not the bidirectional ``startswith`` this used to
        do. That comparison accepted any truncation or extension of a real name:
        ``Code`` passed for ``Code Quality``, and ``CAO MCP Apps E2E`` passed for
        ``CAO MCP Apps E2E (Playwright)`` -- both verified green before this
        change. A contributor searching the PR's checks for the documented name
        finds nothing in either case.
        """
        real = _ci_job_names()
        # Only the FIRST column of a table row names a job -- later columns hold
        # the blocking verdict, which is also bolded.
        claimed = {
            _canonical_job_name(m.strip())
            for m in re.findall(r"^\|\s*\*\*(.+?)\*\*", _skill_text(), re.MULTILINE)
        }
        phantom = sorted(claimed - real)
        assert not phantom, (
            f"The skill documents jobs that no longer exist in ci.yml: {phantom}. "
            f"Real job names: {sorted(real)}. Names must match exactly (matrix "
            "interpolation aside) -- a near-miss is not findable in the PR's checks."
        )


class TestTheGateMapBlockingVerdicts:
    """The ``Blocking?`` column, which was previously unverified prose.

    ``test_every_ci_job_is_documented`` only checks that a job NAME appears
    somewhere in the file, so a job flipping blocking/tolerated -- or a row
    simply claiming the wrong verdict -- used to pass silently. That is the
    drift class this file exists to catch, and the column is the part a
    contributor acts on when deciding whether a red check blocks the merge.
    """

    def test_the_verdict_guard_has_something_to_check(self):
        """Non-vacuity floor, tied to ci.yml rather than to a magic number."""
        rows = _gate_map_job_rows()
        must_document = _ci_job_names() - set(INTENTIONALLY_UNDOCUMENTED)
        assert len(rows) >= len(must_document), (
            f"Parsed only {len(rows)} gate-map job rows ({sorted(rows)}) but ci.yml has "
            f"{len(must_document)} jobs requiring documentation ({sorted(must_document)}). "
            "If the table was restructured, update the row parser -- otherwise the "
            "verdict check below silently verifies fewer rows than it appears to."
        )

    def test_every_row_verdict_is_readable(self):
        unreadable = sorted(
            name for name, cell in _gate_map_job_rows().items() if _claimed_blocking(cell) is None
        )
        assert not unreadable, (
            f"These gate-map rows have no readable Blocking? verdict: {unreadable}. "
            "A cell must say **Yes**, **No**, or 'non-blocking' so the claim can be "
            "checked against ci.yml rather than taken on trust."
        )

    def test_every_row_verdict_matches_job_level_continue_on_error(self):
        jobs = _ci_jobs_by_name()
        wrong: list[str] = []
        for name, cell in sorted(_gate_map_job_rows().items()):
            job = jobs.get(name)
            if job is None:
                continue  # a phantom name is test_no_phantom_jobs_are_documented's finding
            claimed = _claimed_blocking(cell)
            real = _job_is_blocking(job)
            if claimed is not real:
                raw = job.get("continue-on-error", "<unset>")
                wrong.append(
                    f"{name!r}: the skill says "
                    f"{'blocking' if claimed else 'tolerated'}, but ci.yml says "
                    f"{'blocking' if real else 'tolerated'} "
                    f"(job-level continue-on-error={raw!r})"
                )
        assert not wrong, (
            "The gate map's Blocking? column disagrees with ci.yml:\n  "
            + "\n  ".join(wrong)
            + f"\nFix the table in {SKILL.relative_to(REPO_ROOT)} or the job in ci.yml. "
            "A wrong verdict tells a contributor to ignore a gate that will block "
            "their merge, or to chase one that will not."
        )


class TestTheBlockingDerivationItself:
    """Pins ``_job_is_blocking`` directly, because ci.yml cannot exercise it.

    Every job in ci.yml is blocking today, so the gate-map test above would pass
    even if the derivation returned True unconditionally. These assert the branch
    that ci.yml never reaches, so the guard is not merely vacuously green.
    """

    @pytest.mark.parametrize(
        "yaml_fragment,expected_blocking",
        [
            ("", True),  # unset -- GitHub's default is false, i.e. blocking
            ("continue-on-error: false", True),
            ("continue-on-error: true", False),
            ('continue-on-error: "true"', False),  # quoted is still truthy YAML
        ],
    )
    def test_unset_and_false_block_while_true_tolerates(self, yaml_fragment, expected_blocking):
        job = yaml.safe_load("name: Example\n" + (f"{yaml_fragment}\n" if yaml_fragment else ""))
        assert _job_is_blocking(job) is expected_blocking

    def test_step_level_tolerance_does_not_make_the_job_tolerated(self):
        job = yaml.safe_load(
            "name: Example\n"
            "steps:\n"
            "  - run: the real gate\n"
            "  - run: upload an artifact\n"
            "    continue-on-error: true\n"
        )
        assert _job_is_blocking(job) is True

    def test_ci_really_contains_the_step_level_tolerance_just_asserted(self):
        """Keeps the test above honest: the case it models is real, not invented.

        If ci.yml ever stops carrying step-level tolerances, the modelling above
        is no longer describing this repo and should be revisited rather than
        left as decoration.
        """
        tolerated = [
            (job_name, step.get("name"))
            for job_name, job in _ci_jobs_by_name().items()
            for step in (job.get("steps") or [])
            if _truthy_continue_on_error(step.get("continue-on-error"))
        ]
        assert len(tolerated) >= 2, (
            "Expected ci.yml to carry several step-level continue-on-error steps "
            f"(mypy plus the artifact uploads); found {tolerated}."
        )
        assert all(
            _job_is_blocking(_ci_jobs_by_name()[job_name]) for job_name, _ in tolerated
        ), f"A job with a tolerated STEP must still be a blocking JOB: {tolerated}"


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
        match = re.search(r"--cov=(\S+)", _unit_tests_pytest_command())
        assert match, "The Unit Tests job no longer passes --cov; update this test."
        target = match.group(1)
        # Compare exact tokens. A substring check would pass "--cov=src" against a
        # skill saying "--cov=src/cli_agent_orchestrator", which is the very drift
        # this test exists to catch.
        quoted = set(re.findall(r"--cov=([^\s`|)]+)", _skill_text()))
        assert target in quoted, (
            f"The Unit Tests job runs coverage as --cov={target}, but the skill quotes "
            f"{quoted or '{}'}. A wrong coverage target sends contributors looking at "
            "the wrong report."
        )

    def test_the_marker_expression_matches_ci(self):
        match = re.search(r'-m\s+"([^"]+)"', _unit_tests_pytest_command())
        assert match, "The Unit Tests job no longer passes -m; update this test."
        assert match.group(1) in _skill_text(), (
            f'The Unit Tests job deselects with -m "{match.group(1)}"; the skill must '
            "quote it verbatim, because it replaces any local addopts rather than "
            "composing with them."
        )

    def test_the_path_exclusions_are_documented_as_well_as_the_marker(self):
        """``-m "not e2e"`` is not the whole selection, and the difference misleads.

        The Unit Tests job also excludes two paths outright, so the Kiro provider
        integration test does NOT run in CI. Quoting only the marker supports the
        inference that every integration test runs in CI, which is what the skill
        used to say. Pinned in both directions: the flags must still be in ci.yml,
        and the skill must still name them.
        """
        command = _unit_tests_pytest_command()
        missing_from_ci = [flag for flag in CI_REQUIRED_IGNORES if flag not in command]
        assert not missing_from_ci, (
            f"The Unit Tests job no longer passes {missing_from_ci}. The skill's "
            "carve-out for the Kiro integration test is now wrong -- reword it rather "
            "than deleting this assertion."
        )
        text = _skill_text()
        missing_from_skill = [flag for flag in CI_REQUIRED_IGNORES if flag not in text]
        assert not missing_from_skill, (
            f"ci.yml narrows the Unit Tests selection with {missing_from_skill}, which "
            f"{SKILL.relative_to(REPO_ROOT)} does not mention. Without them the skill "
            'implies -m "not e2e" is the whole story and that every integration test '
            "runs in CI; the Kiro provider integration test does not."
        )


class TestTheIsolatedHomeRecipeReallyIsolates:
    """The recipe tells contributors to prove a test is clean-runner-safe.

    It is the one snippet in the skill whose whole purpose is to produce a
    trustworthy pass/fail signal, so a recipe that reports the wrong answer is
    worse than no recipe: it manufactures the confidence it was supposed to
    test for. Two ways it could, both verified against the real code rather
    than assumed:

    * Overriding ``HOME`` alone does not relocate CAO's state. ``constants.py``
      prefers an exported ``CAO_HOME_DIR`` and derives ``DB_DIR`` and every
      other state path from it, so a contributor who already exports an
      absolute (or cwd-relative) value keeps using the initialised store the
      recipe is meant to exclude -- concealing exactly the missing-table
      failure it exists to surface. A tilde-relative value does follow ``HOME``,
      which is why this reads as working when spot-checked.
    * Cleaning up with ``;`` discards the test's exit status and yields the
      status of ``rm``. An agent or script checking the status reads a failing
      run as a pass. ``&&`` is not the fix -- it leaks the temporary directory
      on failure, which is the case you most want cleaned up.
    """

    def test_the_env_var_the_recipe_overrides_is_the_one_constants_reads(self):
        """Anchor the guard to the code, not to a remembered variable name."""
        source = (REPO_ROOT / "src" / "cli_agent_orchestrator" / "constants.py").read_text()
        assert 'os.environ.get("CAO_HOME_DIR"' in source, (
            "constants.py no longer reads CAO_HOME_DIR from the environment. The "
            "isolated-HOME recipe overrides that variable; if the override moved, "
            "update the recipe and this guard together."
        )

    def test_it_overrides_cao_home_dir_as_well_as_home(self):
        recipe = _isolated_home_recipe()
        assert "CAO_HOME_DIR=" in recipe, (
            "The isolated-HOME recipe sets HOME but not CAO_HOME_DIR, so a "
            "contributor exporting an absolute CAO_HOME_DIR keeps the real "
            f"database. Recipe:\n{recipe}"
        )

    def test_the_override_points_inside_the_throwaway_directory(self):
        """An override that is not under the temp dir isolates nothing."""
        recipe = _isolated_home_recipe()
        assigned = re.search(r"CAO_HOME_DIR=\"?([^\s\"]+)", recipe)
        assert assigned, f"Could not read the CAO_HOME_DIR value from:\n{recipe}"
        value = assigned.group(1)
        assert "$TMPH" in value, (
            f"CAO_HOME_DIR is set to {value!r}, which is not under the mktemp "
            "directory, so CAO's state still lives outside the throwaway home."
        )

    def test_cleanup_preserves_the_test_exit_status(self):
        recipe = _isolated_home_recipe()
        assert "trap " in recipe, (
            "The recipe must clean up via a trap in a subshell so the pytest exit "
            "status survives. Verified empirically: with `; rm -rf` a pytest exit "
            "of 1 and of 2 both surfaced as 0; with the trap form, 1, 2 and 0 each "
            f"surfaced unchanged and no temp dir leaked. Recipe:\n{recipe}"
        )
        offending = [
            line
            for line in recipe.splitlines()
            if re.search(r"pytest.*;\s*rm\s+-rf", line) or re.search(r"&&\s*rm\s+-rf", line)
        ]
        assert not offending, (
            "Cleanup is chained to the pytest command in a way that either "
            f"discards its status (';') or leaks the temp dir on failure ('&&'): {offending}"
        )


class TestReferencedPathsExist:
    def test_the_example_path_guard_has_something_to_check(self):
        """Floor for the parametrize below, which is evaluated at COLLECTION time.

        If those backticked ``examples/`` paths are reworded away, ``findall``
        returns ``[]``, the parametrized guard collects ZERO tests, and the suite
        reports success -- the failure mode is silence, not red.
        ``test_the_reference_guard_has_something_to_check`` is the floor for a
        DIFFERENT matcher (skill names) and does not cover this site.
        """
        found = _referenced_example_paths()
        assert len(found) >= MINIMUM_EXAMPLE_PATH_REFERENCES, (
            f"Expected at least {MINIMUM_EXAMPLE_PATH_REFERENCES} backtick-quoted "
            f"examples/ paths in {SKILL.relative_to(REPO_ROOT)}, found {found}. If the "
            "recorder sections were reworded, lower this floor deliberately -- the "
            "parametrized existence check below collects nothing without it."
        )

    @pytest.mark.parametrize("quoted", re.findall(EXAMPLE_PATH_PATTERN, SKILL.read_text()))
    def test_every_referenced_example_path_exists(self, quoted: str):
        path = REPO_ROOT / quoted.rstrip("/")
        assert path.exists(), (
            f"The skill references {quoted}, which does not exist. "
            "Paths in a skill are instructions an agent will follow literally."
        )


class TestMypyToleranceClaim:
    def test_mypy_is_still_non_blocking(self):
        """The skill tells contributors not to 'fix' red mypy. Verify that holds."""
        spec = _ci_spec()
        steps = spec["jobs"]["lint"]["steps"]
        mypy_steps = [s for s in steps if "mypy" in str(s.get("run", ""))]
        assert mypy_steps, "The lint job no longer runs mypy; update the skill."
        assert all(_truthy_continue_on_error(s.get("continue-on-error")) for s in mypy_steps), (
            "mypy is now BLOCKING in CI. The skill's guidance to ignore pre-existing "
            "mypy errors is actively harmful until it is rewritten."
        )


# NOTE: there is deliberately no test here that the packaged mirror matches
# ``skills/cao-contributing/SKILL.md``. It would duplicate
# ``test/test_skill_packaging_parity.py::TestPackagingParity``
# ``::test_every_file_is_byte_identical[cao-contributing]``, which auto-parametrizes
# over ``SHIPPED_SKILLS`` and compares with ``filecmp.cmp(..., shallow=False)`` over
# EVERY file in the skill directory -- a strict superset of a single ``SKILL.md``
# text comparison. Removed rather than kept after confirming that test id is
# collected; re-add only if cao-contributing ever leaves ``SHIPPED_SKILLS``.
