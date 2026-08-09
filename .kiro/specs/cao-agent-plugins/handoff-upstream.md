# Handoff: local audit, signed single commit, dog-food recordings, upstream PR

**Audience:** `kiro-cli`, running **locally** on plauzy's machine, with a signing key and a
real CAO installation.

**Why this file exists.** Four things this change needs cannot be done from the Kiro Web
sandbox where it was built, and pretending otherwise would put unverifiable claims in front
of upstream reviewers:

| Needed | Why the sandbox cannot do it |
|---|---|
| **Signed commits** | No GPG/SSH signing key. All eight commits are `verified=false, reason=unsigned` — confirmed via the API, not assumed. |
| **Dog-food recordings** | Recording a real `cao plugin add` → provider-launch flow needs a real CAO install, real provider CLIs, and a display/Chromium. |
| **AC2's tools-callable half** | Needs two real foreign clients actually calling `cao-ops` tools. Deliberately **not claimed** in PR #36 for exactly this reason. |
| **Upstream PR** | Should carry signed commits and the recordings, so it goes last. |

Everything else is done and verified. This file is the instruction set, not a summary —
§1 is the state you can rely on without re-deriving it.

**Delete this file in the collapse step (§3).** It is internal process; upstream reviewers
reading `.kiro/specs/` do not need our signing runbook.

---

## 1. State you can rely on

**Branch:** `claude/cao-agent-plugins-impl-1id3pg` @ `5563801` (fork `plauzy/cli-agent-orchestrator`, PR #36, draft).

**Fork `main` is in sync with `upstream/main` at `5464a2e`**, and every commit this branch
merged from `main` (`5464a2e`, `e41a731`, `38527f4`, `c7aff4b`) exists upstream. That is what
makes §3's collapse conflict-free.

Eight commits on top of the pre-reconcile head `2d69333`:

```
5563801  fix(agent-plugins): failed-replace recovery, CAO-vs-plugin fault, warning everywhere (WP4.4-4.6)
4a87106  test(agent-plugins): port the property-test tier from impl (WP4.3)
f95436c  feat(agent-plugins): port resolver git hardening from impl (WP4.2)
93e53d5  test(agent-plugins): port the docs-guard suite from impl (WP4.1)
a099309  fix(agent-plugins): ride-along audit findings R3, R4 and R5
05b74e2  fix(api): gate GET /plugins on the read floor and hoist its session walk (R2)
4f2d523  feat(agent-plugins): deliver plugin MCP servers into agent profiles (R1)
7962519  Merge branch 'main' into claude/cao-agent-plugins-impl-1id3pg
```

**CI on `5563801`: 18 success, 1 skipped, 0 failures.** First fully-clean run this PR has had.

**Test counts (all measured, not estimated):**

```
6950 passed, 42 skipped, 1 xfailed    full Python suite
 594 passed,  3 skipped               test/agent_plugins/
  29 passed                           test/test_agent_plugins_docs.py
  90 passed                           test/plugins/ (event plugins — D7 untouched)
  22 passed                           conformance corpus (exact-match)
 106 passed                           web (vitest)
 143 passed                           Rust TUI
```

**The 62 remaining Python failures are pre-existing.** Established by set comparison, not
assertion: failing test names captured from a full run on this branch and on `main` at
`5464a2e`, sorted, compared both directions — identical. Re-run that comparison locally if
you want to confirm; do not spend time trying to fix them. They are 43 in
`test/services/agui`, 15 AG-UI tests in `test/api`, 3 OpenTelemetry, and
`test_expands_home` (which fails only because the sandbox runs as root, so `~` resolves to
the blocked `/root` — **this one may well pass on your machine**, which is expected and not
a discrepancy to chase).

**Backups, do not force-push over these:** `backup/pr36-pre-reconcile` @ `2d69333`,
`backup/pr36-original-history` @ `9cf1f90`.

**Read `docs/audits/agent-plugins-adoption-audit.md`** (branch
`claude/cao-agent-plugins-audit-o9mtw1`, PR #37) before auditing. Findings R1–R5 are all
fixed; the closing comment on PR #36 maps each to its commit.

---

## 2. Task A — audit locally

The point is an independent read, not a re-run of what CI already proves. **Do not
re-litigate decisions already recorded** in `design.md` §10a, the Requirement 13 amendment
note, or the PR description — challenge them if they are wrong, but they were reasoned, and
the reasoning is written down.

### Verify rather than trust

1. **`uv run pytest`, then compare the failure set to `main`** — the claim is *identical
   sets*, not merely equal counts. `git worktree add /tmp/main-base upstream/main`, run both,
   `comm` the sorted `FAILED` lists.
2. **The mutation checks.** Every new behaviour was confirmed to fail when the thing it
   asserts is removed. Spot-check two you care about — the recipe is: back up the source
   file, patch out the feature, run the targeted test file, restore. Documented per commit.
3. **`make check-agent-plugins-schemas`** and confirm the vendored `*.schema.json` bytes are
   untouched: `git diff 2d69333..5563801 -- src/cli_agent_orchestrator/schemas/agent_plugins/`
   should show **only** `PIN.json`, `+1` line (the new `pin_policy`).
4. **The three M1 ship-gates are closed** — `hidden=True` on the Click group, four
   `Policy::Hidden` rows in `tui/src/catalog.rs`, `PLUGINS_TAB_ENABLED = false`. Each has a
   test asserting the *closed* state.

### Where I would want a second pair of eyes

Named honestly, highest-risk first:

1. **`install_service.refresh_installed_agents_for_plugin_mcp()`** — the widest blast radius
   in the change. It re-runs the real `install_agent()` for every CAO-managed installed agent
   on plugin install/uninstall. Idempotent by design and best-effort by contract, but it
   **rewrites provider config files on a machine that has real agents installed**, and the
   sandbox had none. This is the single thing most worth exercising on a real install before
   it goes upstream. Check in particular that an agent whose source profile has since been
   deleted degrades to a logged warning and does not leave a half-written config.

   **A known defect lives here — see §2a. Do not treat it as a finding to discover.** The
   refresh closes the removal gap for Kiro and Copilot but **not for OpenCode**, and the
   consequence collides with dog-food step 5. Read §2a before building the recorder.
2. **The `_UNRESOLVABLE` sentinel** in `installer.py` — a module-level `List[str]` used as an
   identity sentinel, compared with `is`. Distinguishing it from `skills=None` (which
   legitimately means "no filter, receives every skill") is load-bearing: conflating them
   would report a deleted-profile terminal as affected by every plugin. It works, but a
   sentinel object compared by identity is the kind of thing a refactor breaks silently.
   Consider whether an `enum` or a dedicated class reads better.
3. **`store.publish()`'s failure path.** The `preserved, backup = backup, None` before the
   `raise` is the entire fix for a data-loss bug (`finally` was sweeping the only remaining
   copy). Injected-failure tests cover it, but injected-failure tests are only as good as the
   injection points. Sanity-check the reasoning.
4. **`_OPEN_READS` in `test/api/test_scope_coverage.py`** — 28 pre-existing ungated GET routes
   pinned as data so a *new* ungated GET fails the build. I deliberately did **not** gate the
   other 28; that would change shipped routes' auth posture. The comment marks the live
   session/terminal reads as the strongest candidates for a future gate. Confirm you agree
   with the scope call, because it is a security-posture judgement, not a mechanical one.
5. **Requirement 18 Criteria 9–12** are additions I made to the spec to state the delivery
   obligation the mapper's design already presupposed. Confirm the spec edit is legitimate
   rather than the implementation retrofitting its own requirements.

### 2a. Known defect — OpenCode's removal path (blocks dog-food step 5 as written)

Raised in review on PR #36 and **reproduced independently against the helpers on `5563801`**
before being written down here. Two findings, one root cause.

**Root cause.** Kiro's `<name>.json` and Copilot's `<name>.agent.md` are rewritten *wholesale*
on every replay (`model_dump_json` at `install_service.py:441`, `frontmatter.dumps` at `:464`),
so a server no longer in `profile.mcpServers` simply is not written and is gone. OpenCode's
shared `opencode.json` is **edited in place**, and `upsert_mcp_server` is upsert-only
(`opencode_config.py:131` — its own docstring says "Name collisions silently overwrite the
prior `mcp` entry"). There is **no `remove_mcp_server` anywhere in the tree**, and nothing
else deletes from the `mcp` section.

**Finding 1 — a removed plugin's server survives uninstall.** The `else` branch at
`install_service.py:507-508` calls `remove_agent_tools()`, which withdraws the per-agent
*grant* but leaves the *server*. Reproduced:

```
after install                                  after uninstall + refresh
  mcp: {plugin-srv: {command: [...          mcp: {plugin-srv: {command: [...
        /agent-plugins/demo], enabled:            /agent-plugins/demo],  ← root DELETED
        true}}                                    enabled: true}}        ← still true
  agent: {worker: {tools:                    agent: {}                  ← grant correctly gone
        {plugin-srv*: true}}}
```

`enabled` is server-level, so withdrawing the per-agent grant does not stop OpenCode
launching the process — it governs which agent may *call* the tools. Net effect: a spawn
attempt against a missing executable on every OpenCode launch, permanently, for every plugin
ever installed and removed.

**Finding 2 — a plugin server silently clobbers a user's hand-written entry.** Same upsert.
Seeding `opencode.json` with a user's own `plugin-srv`, then installing a plugin declaring
that name, replaces the user's command with **no finding emitted**. `merge_plugin_mcp_servers`'
"the profile always wins" rule is real but scoped to the *agent profile's* `mcpServers`;
OpenCode's shared config is a second namespace the profile-level rule never sees.

**Why it was reported rather than fixed.** Closing it needs a decision, not just a function:
`map_and_merge` deliberately does not namespace plugin server names
(`mcp_delivery.py` — "Renaming would be worse than dropping", which is the right call), so
`opencode.json` has no provenance separating a plugin's `foo` from a user's `foo`.

| Option | Trade |
|---|---|
| 1. Record delivered server names in the install record, prune exactly those | Precise. Adds persisted state R1 avoided — though note *names* are stable identifiers and do not go stale the way the absolute-path expansions would, so this is weaker than it first appears |
| 2. Mark CAO-managed entries (`x-cao-plugin: <name>`) and prune by marker | Self-describing, survives `CAO_HOME_DIR` moves. Writes a non-standard key into a file OpenCode owns |
| 3. Set `enabled: false` instead of deleting | Smallest blast radius, stops the spawn, CAO never deletes a key it may not own. Leaves inert cruft |

**Recommendation: 3 for this PR, then 1 or 2 as a follow-up** — it fixes the actual harm
without CAO deleting anything it cannot prove it owns. Finding 2 additionally wants an
install-side guard: emit a finding when an incoming plugin server name already exists in
`opencode.json` and was not placed by CAO. **Confirm the choice with the maintainer before
implementing** — the reviewer offered to take it, so check for in-flight work first.

Until it is fixed, `design.md` §10a and `docs/agent-plugins.md` overclaim: both say removal
withdraws the servers, which holds for two of three providers. Correct the wording in the same
change as the fix.

### Known-imperfect, already recorded

- The **increment-boundary deviation** (`tasks.md` sequences W11 behind W5 *merging*; this
  ships both). Named in the PR description with the reason and an offer to split.
- The **documentation-vocabulary backlog** — seven docs using bare "plugin" for the
  event-plugin system, listed in `test_naming_migration.py::_VOCABULARY_BACKLOG_DOCS` rather
  than silently skipped. Fixing them is ~12 prose edits and was judged out of scope.
- **`a099309`'s commit message says "500 passed"** for `test/agent_plugins/`; the true figure
  at that commit was 514. A stale number in a commit message, not in the code. The PR
  description carries the correct current figure (594). Do not "fix" it by rewriting history
  for its own sake — it disappears in the collapse anyway.

---

## 3. Task B — sign and collapse into one commit

### The recipe, verified

I dry-ran this in a scratch worktree and confirmed the resulting tree is **byte-identical**
to `5563801`'s tree (`115db3ee…`), with exactly one parent and no conflicts:

```bash
git remote add upstream https://github.com/awslabs/cli-agent-orchestrator.git   # if absent
git fetch upstream main

git switch -c feat/agent-plugins-573-upstream upstream/main
git merge --squash 5563801        # stages the whole change; applies cleanly
git rm -q .kiro/specs/cao-agent-plugins/handoff-upstream.md   # this file: internal only

git commit -S -F .git/COMMIT_MSG_agent_plugins   # message drafted below

# Prove the collapse preserved the content (minus this file):
git diff --stat 5563801 HEAD      # expect: only handoff-upstream.md deleted
git log -1 --format='%G? %GK %an <%ae>'   # expect a good signature
```

`git merge --squash` rather than `reset --soft`: it handles adds, deletes and renames
correctly across the merge commit in the middle of the history, which a soft reset over a
merge does not.

### Authorship and trailers

The repo convention, and the user's standing instruction, is **both** co-author trailers on
every commit made on their behalf:

```
Co-authored-by: plauzy <4451274+plauzy@users.noreply.github.com>
Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>
```

Author/committer should be plauzy's real signing identity, so the signature verifies. Note
the eight spec commits beneath (`c7aff4b..9241c61`) are authored `Kiro Agent` with both
trailers — that is the established shape; match it.

### The "unverified commits" fix

`reason=unsigned` on all eight. Signing the single collapsed commit resolves it for the
upstream PR. Confirm signing is actually configured before committing, rather than after:

```bash
git config --get user.signingkey
git config --get commit.gpgsign
git config --get gpg.format          # "ssh" if using an SSH signing key
```

If upstream requires the fork's PR head to be verified too, re-sign the fork branch as well;
otherwise leaving PR #36's history unsigned is harmless, since the upstream PR is the
artifact that matters. **Do not force-push over either `backup/*` ref.**

### Commit message

Reuse the PR #36 description as the body — it is already structured for this — but lead with
a subject that names the issue, and keep the "how it was verified" section, because that is
what a reviewer who does not know this branch needs:

```
feat(agent-plugins): Agent Plugins 1.0.0 support (#573)
```

---

## 4. Task C — shift-left dog-food recordings

### Follow the repo's own convention; do not invent one

This repo already has three gated recorders. Read one before writing anything:

- `examples/ag-ui/ag-ui-construct-demos/tools/record-construct-demos.mjs` — the closest model
- `examples/ag-ui/ag-ui-eventsource-viewer/tools/record-demo.mjs`
- `cao_mcp_apps/scripts/record-demo.mjs`

The convention, in its own words: *"The recording is GATED (this is the shift-left test): if
an example exits non-zero … the recorder exits non-zero and fails CI. The GIFs are
proof-of-work, not decoration — a broken construct cannot produce a green recording."*

Concretely: recorder at `<example-dir>/tools/record-*.mjs`, its own `package.json` with
`record` + `playwright:install` scripts, `@playwright/test` + `ffmpeg-static` as
devDependencies, output to `docs/media/<slug>-demo.gif`, and a CI job named
`... (shift-left recording)` that uploads the GIF as an artifact. Existing GIFs are committed
directly (not LFS) at 300 KB – 2.1 MB; stay in that range.

**The recording must assert, not narrate.** A GIF that would still render if the feature
were broken is decoration and should not be added.

### What to record — the feature validating itself

Dog-fooding here has an exact meaning: **install CAO's own packages through CAO's own new
plugin pipeline.** Suggested gated sequence, each step asserting and exiting non-zero on
drift:

1. `cao plugin validate agent-plugin/cao` → loadable, the four skills named
   (`cao-session-management`, `cao-agent-routing`, `cao-supervisor-protocols`,
   `cao-worker-protocols`), `mcp_present: true`.
2. `cao plugin add ./agent-plugin/cao` → installed; assert the skills are **projected** into
   the skill store as symlinks pointing into the plugin store (`ls -l` is the visual, the
   assertion is on the link target).
3. `cao install <profile> --provider kiro_cli` → assert the emitted agent JSON contains
   **both** `skill://` globs **and** the `cao-ops` server with `${PLUGIN_ROOT}` expanded to a
   real path, no `x-cao-pre-expanded` marker, and `PLUGIN_ROOT`/`PLUGIN_DATA` in `env`. This
   is the R1 fix visible end to end, and it is the step no sandbox test could show against a
   real provider config.
4. **Call a `cao-ops` tool from a real client.** See below — this is the valuable one.
5. `cao plugin remove cao` → assert the `cao-ops` server **disappears** from the provider
   config. This is the refresh path, and it is the half most likely to be doubted.

   > **Read §2a first — this step cannot pass as originally written.** Removal works for
   > **Kiro** (which step 3 installs) and Copilot, and **fails for OpenCode**, whose server
   > entry survives with `enabled: true`. A gated recorder asserting "disappears" against
   > OpenCode will go red at recording time, and **the recorder will be right** — whoever
   > builds it would otherwise spend the afternoon debugging correct tooling.
   >
   > Pick one, in preference order:
   >
   > - **Fix §2a first, then record both providers.** Best outcome: the step becomes real
   >   cross-provider proof instead of a single-provider demo.
   > - **Record Kiro only, and say so on screen** — name the provider in the caption and add
   >   a frame stating OpenCode is tracked as a known gap. A demo that asserts removal works,
   >   filmed against the one provider where it does, is proof-of-work that ages badly, and a
   >   GIF is not diffable.
   >
   > What is **not** acceptable is asserting removal generically while filming Kiro. That
   > reads as a cross-provider guarantee and is not one.

Narrate one subtlety on screen or the viewer will be confused: **`cao plugin` is
`hidden=True`** pending decision M1, so it does not appear in `cao --help`. It is reachable
and fully usable; it is deliberately unadvertised. A demo of an intentionally hidden command
needs to say so.

### The AC2 opportunity — the highest-value thing this local run can produce

Issue #573's AC2 requires the `cao` package to install and work in **≥2 compatible clients**,
with `cao-ops` tools *callable* and `cao-session-management` *discovered*. The skill half is
covered by tests. **The tools-callable half is explicitly not claimed in PR #36**, because it
needs real foreign-client runs.

You can close it. Two clients, install `agent-plugin/cao` into each, call a `cao-ops` tool,
record it. If you do, say so precisely in the upstream PR — name the two clients and their
versions — and only then move AC2 from "not claimed" to "met". If you cannot get two clients
working, **leave the claim exactly as it is**; an unverified AC is much worse than an
acknowledged gap.

### Recording safety — a real incident, read this

`CONTRIBUTING.md` § *Recording test fixtures safely* exists because **incident #436 merged
personal emails** into this repo from captured CLI output, and PR #456 had to scrub them. A
GIF of your real machine is exactly that risk class, and worse, because a GIF is not
diffable.

Before committing any recording:

- **Scrub identity.** Real home paths (`/Users/<name>`, `/home/<name>`), account emails,
  hostnames, org names. Use a synthetic home or a throwaway account. `PLUGIN_ROOT` paths are
  *shown deliberately* in step 3 — make sure the path you show is not
  `/Users/<yourname>/...`.
- **Skim raw bytes, not the render.** Secrets hide next to ANSI escapes and are invisible in
  a normal terminal view. That was the #436 mechanism.
- **Prefer the reserved placeholders** scanners treat as safe: `user@example.com`, and for
  AWS `AKIAIOSFODNN7EXAMPLE`.
- **Run the scanner:** `scripts/security-scan.sh gitleaks`. A gitleaks scan runs on every PR
  and weekly over full history; catching it locally is cheaper than a history rewrite.
- If a provider prints a login banner with an email, that frame does not belong in the GIF.

### Where the evidence lands

- GIFs → `docs/media/agent-plugins-*-demo.gif`
- A short **"Verified by dog-fooding"** section in `docs/agent-plugins.md` embedding them and
  stating what each asserts. Prose alone is not the evidence; the gate is.
- A CI job so the recording keeps being a test rather than becoming a stale artifact.
- If any recorder step needs real provider binaries CI does not have, gate that step behind
  an env flag and keep the offline steps running in CI — matching how the AG-UI recorders run
  in "offline/synthetic mode … no live provider, network, or secrets required."

---

## 5. Task D — upstream PR

### Prerequisites, from `CONTRIBUTING.md`

- **Against latest `main`** — §3's recipe does this by construction.
- **An issue exists for significant work.** [awslabs#573](https://github.com/awslabs/cli-agent-orchestrator/issues/573)
  is open and filed by plauzy. Link it in the PR body and use `Closes #573` **only if** AC2 is
  genuinely met (see §4); otherwise reference it without closing and say which AC remains.
- **Focused change, no drive-by reformatting.** Worth re-checking the collapsed diff for
  stray formatting churn: `git diff upstream/main HEAD --stat` should be all
  agent-plugins-related. The seven `examples/fleet/` files that `black --check .` flags are
  **pre-existing on `main`** — do not reformat them, that is exactly the noise CONTRIBUTING
  asks contributors to avoid.
- **Local tests pass** — §2.
- **Licensing.** CONTRIBUTING says *"We will ask you to confirm the licensing of your
  contribution."* Confirm it in the PR body proactively.

### Branch naming

This fork's prior upstream PRs use an `-upstream` suffix, and the signed one used `-signed`
(`agui-phase2-458-upstream` → awslabs#485, `fix/gh-pages-fork-deploy-gate-upstream` →
awslabs#574, `kiro/pr387-phase-a-agui-core-signed` → awslabs#436). `feat/agent-plugins-573-upstream`
follows it.

### Opening it

**`gh pr create` is GraphQL-backed and fails in the Kiro Web sandbox; it should work fine
locally.** If it does not, the REST fallback is:

```bash
gh api repos/awslabs/cli-agent-orchestrator/pulls \
  -f title="feat(agent-plugins): Agent Plugins 1.0.0 support (#573)" \
  -f head="plauzy:feat/agent-plugins-573-upstream" \
  -f base="main" \
  -f body="$(cat /path/to/body.md)"
```

Note the `owner:branch` form in `head` for a cross-repo PR.

### PR body

Start from PR #36's description — it is written for reviewers who do not know the branch —
and change four things:

1. **Drop the fork-internal framing.** The reconciliation-with-the-audit narrative, the
   `backup/*` refs, and the "PR #36 / PR #37" cross-references mean nothing upstream. Keep
   the *substance* of the audit fixes (they are real improvements); drop the process story.
2. **Add the dog-food evidence** — embed the GIFs, state what each asserts, and name the
   clients used for AC2 if you closed it.
3. **State the increment-boundary deviation** and the offer to split, as PR #36 does.
4. **Keep the honest gaps**: M1–M4 open, the vocabulary backlog, and AC2 if still unclaimed.
   Upstream maintainers will find these anyway; naming them first is why the PR gets trusted.

### After opening

Watch CI on the **upstream** runner — it is not identical to the fork's. In particular
`test_expands_home` failed in the sandbox only because it ran as root; on a normal runner it
should pass, which changes the expected failure count. Do not report the sandbox's 62-failure
baseline as though it applies upstream; re-derive it against upstream `main` if you need to
state one.

---

## 6. Non-goals — do not do these

- **Do not touch `impl/cao-agent-plugins`.** Read-only donor. Its web surface does not parse
  (`web/src/api.ts`) and its canonical-example tests hardcode a sandbox path. Retiring it is
  a separate decision; PR #36's closing comment raises it.
- **Do not resolve M1–M4.** Maintainers' decisions. Every surface they gate is built, tested
  and closed.
- **Do not open the ship-gates** to make a nicer demo. If the recording needs the web Plugins
  tab, flip the flag *in the recorder's environment*, never in committed source, and say so
  on screen.
- **Do not chase the 62 pre-existing failures**, and do not "fix" `examples/fleet/`
  formatting.
- **Do not modify the event-plugin system** (`src/cli_agent_orchestrator/plugins/`). Design
  decision D7; its diff across the whole reconcile is empty and should stay that way.
- **Do not change vendored schema bytes or the recorded `sha256`s.** Only `PIN.json`'s new
  `pin_policy` field was added.

---

## 7. Definition of done

- [ ] Local audit complete; the five review areas in §2 either confirmed or raised as
      findings.
- [ ] Failure-set comparison re-run locally against `upstream/main`.
- [ ] One **signed** commit on `feat/agent-plugins-573-upstream`, parent `upstream/main`,
      both co-author trailers, tree verified against `5563801` (minus this file).
- [ ] At least one **gated** recorder committed, exiting non-zero on drift, with its GIF in
      `docs/media/` and a CI job running it.
- [ ] Recordings scrubbed; `scripts/security-scan.sh gitleaks` clean.
- [ ] `docs/agent-plugins.md` has a "Verified by dog-fooding" section embedding the evidence.
- [ ] AC2 either **closed with named clients and versions**, or left explicitly unclaimed.
- [ ] §2a (OpenCode removal) either **fixed**, with `design.md` §10a and
      `docs/agent-plugins.md` corrected in the same change, or carried into the upstream PR
      body as a stated known gap. Dog-food step 5 must match whichever was chosen.
- [ ] Upstream PR open against `awslabs/cli-agent-orchestrator:main`, referencing #573,
      licensing confirmed, honest gaps stated.
- [ ] Upstream CI green, or every failure explained against an upstream-`main` baseline.
