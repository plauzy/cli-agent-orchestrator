"""Refinery Preflight: Code-Review-Loop stage (vision addendum §10).

Spawns a fresh-context Reviewer via CAO handoff so it shares zero
accumulated context with the coder — Cognition's research shows this
is the architectural primitive that makes the Code-Review Loop work.

The reviewer receives only the diff as input and reasons backward from
the implementation. The Mayor filters findings against user intent
before deciding whether to iterate.

Gated on ``REFINERY_CODE_REVIEW_ENABLED=true`` (default off).
Target SLO: ≥1.5 severe findings/PR caught.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

REFINERY_CODE_REVIEW_ENABLED: bool = (
    os.getenv("REFINERY_CODE_REVIEW_ENABLED", "false").lower() == "true"
)

# Reviewer profile to spawn for each review iteration. Must be installed
# via `cao install reviewer` before the preflight stage can be used.
REVIEWER_AGENT_PROFILE: str = os.getenv("REFINERY_REVIEWER_PROFILE", "reviewer")

# Provider for the Reviewer Polecat. Cross-frontier diversity boosts
# review value per Cognition's finding — default differs from the coder.
REVIEWER_PROVIDER: str = os.getenv("REFINERY_REVIEWER_PROVIDER", "claude_code")


@dataclass
class ReviewerFinding:
    severity: str  # "severe" | "minor" | "nit"
    category: str  # "logic" | "edge-case" | "security" | "style"
    location: str  # "file:line" or free-form description
    description: str
    suggested_fix: str | None = None


@dataclass
class PreflightResult:
    findings: list[ReviewerFinding]
    total_severe: int
    iterations_run: int
    skipped: bool = False  # True when REFINERY_CODE_REVIEW_ENABLED=false


def _parse_findings(raw: str) -> list[ReviewerFinding]:
    """Extract structured findings from a Reviewer's free-form output.

    Format expected from the reviewer prompt:
      FINDING: <severity> | <category> | <location> | <description> | <fix?>
    Falls back gracefully to a single nit-level finding with the raw text.
    """
    findings: list[ReviewerFinding] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("FINDING:"):
            continue
        parts = [p.strip() for p in stripped[len("FINDING:") :].split("|")]
        if len(parts) < 4:
            continue
        findings.append(
            ReviewerFinding(
                severity=(
                    parts[0].lower() if parts[0].lower() in ("severe", "minor", "nit") else "nit"
                ),
                category=parts[1],
                location=parts[2],
                description=parts[3],
                suggested_fix=parts[4] if len(parts) > 4 else None,
            )
        )
    if not findings and raw.strip():
        findings.append(
            ReviewerFinding(
                severity="nit",
                category="general",
                location="unknown",
                description=raw.strip()[:200],
            )
        )
    return findings


def _reviewer_prompt(diff: str, iteration: int) -> str:
    return f"""\
You are a fresh-context code reviewer. You have NO prior context about this codebase.
Reason backward from this diff alone.

ITERATION: {iteration}

DIFF:
{diff}

For each issue you find, output exactly one line per finding in this format:
FINDING: <severity> | <category> | <location> | <description> | <suggested_fix>

Where:
  severity  = severe | minor | nit
  category  = logic | edge-case | security | style | performance | other
  location  = filename:line or function name
  suggested_fix = one-line fix suggestion (optional, omit if none)

Report ONLY real issues. Do not invent findings. If the code is correct, output nothing.
"""


async def run_review_loop(
    diff: str,
    *,
    handoff_fn: Any,
    max_iterations: int = 2,
    severe_threshold: int = 0,
) -> PreflightResult:
    """Run review iterations until findings are below threshold or exhausted.

    ``handoff_fn`` must be an async callable matching the signature:
      async def handoff(message, agent_profile, provider) -> str
    Pass the MCP handoff function from the server context.

    Returns immediately with ``skipped=True`` when
    ``REFINERY_CODE_REVIEW_ENABLED=false``.
    """
    if not REFINERY_CODE_REVIEW_ENABLED:
        return PreflightResult(findings=[], total_severe=0, iterations_run=0, skipped=True)

    all_findings: list[ReviewerFinding] = []
    iteration = 0

    while iteration < max_iterations:
        prompt = _reviewer_prompt(diff, iteration)
        try:
            raw_output: str = await handoff_fn(
                message=prompt,
                agent_profile=REVIEWER_AGENT_PROFILE,
                provider=REVIEWER_PROVIDER,
            )
        except Exception:
            logger.warning("Preflight review iteration %d failed", iteration, exc_info=True)
            break

        findings = _parse_findings(raw_output)
        severe_count = sum(1 for f in findings if f.severity == "severe")
        all_findings = findings
        iteration += 1

        logger.info(
            "Preflight iteration %d: %d findings (%d severe)",
            iteration,
            len(findings),
            severe_count,
        )

        if severe_count <= severe_threshold:
            break

    total_severe = sum(1 for f in all_findings if f.severity == "severe")
    return PreflightResult(
        findings=all_findings,
        total_severe=total_severe,
        iterations_run=iteration,
    )
