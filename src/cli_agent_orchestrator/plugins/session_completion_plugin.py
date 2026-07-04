"""Session completion plugin — queues active .sop plans for audit on session kill."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from cli_agent_orchestrator.plugins.base import CaoPlugin, hook
from cli_agent_orchestrator.plugins.events import PostKillSessionEvent

logger = logging.getLogger(__name__)

_SOP_ACTIVE = Path("/Volumes/workplace/.sop/plans/active")
_QUEUE_FILE = Path.home() / ".cao" / "logs" / "completion-queue.jsonl"


class SessionCompletionPlugin(CaoPlugin):
    """Queues .sop/plans/active/ plan files for audit when a CAO session is killed.

    Does NOT launch the audit automatically — only appends a pending entry to
    completion-queue.jsonl. Human or 'cao flow run plan-completion-audit' triggers
    the actual audit. This keeps token spend under user control.
    """

    @hook("post_kill_session")
    async def on_session_kill(self, event: PostKillSessionEvent) -> None:
        if not _SOP_ACTIVE.exists():
            return

        plans = list(_SOP_ACTIVE.glob("*.md"))
        if not plans:
            return

        _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).isoformat()
        for plan in plans:
            entry = {
                "ts": ts,
                "session_id": event.session_id or "unknown",
                "plan_file": str(plan),
                "status": "pending",
            }
            with _QUEUE_FILE.open("a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info("[session-completion] queued for audit: %s", plan.name)

        print(
            f"[session-completion] {len(plans)} plan audit(s) queued. "
            "Run /session-completion or: cao flow run plan-completion-audit"
        )
