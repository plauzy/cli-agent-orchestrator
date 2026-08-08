"""§4.1 path containment for plugin packages.

§4.1 rule 3: when a client discovers, reads, or executes a path supplied by a
plugin package, the **filesystem-resolved** path must remain within the
filesystem-resolved plugin root. Symlinks may resolve to targets inside the
root; paths resolving outside it must be rejected.

"Filesystem-resolved" is the load-bearing word. A lexical check (does the
string contain ``..``?) is not sufficient and not what the spec asks for: a
symlink whose *name* looks innocent can resolve anywhere, and conversely a path
containing ``..`` may resolve back inside the root perfectly legitimately.
Everything here is therefore realpath-based.

Relationship to ``utils/path_validation.py``
--------------------------------------------
``safe_join_under_base`` realpath-canonicalizes and guards containment too, but
it validates *individual path components* against a strict allowlist and joins
them. That is the right shape for CAO-controlled names (a plugin name, a
skill name) and the wrong shape for §4.1's cases, which are an already-existing
path discovered by directory traversal and a ``./``-rooted value read out of a
config file. This module is therefore a sibling using the same
realpath-then-guard technique, not a replacement — the CodeQL taint model and
the security-review posture carry over unchanged.

The failure ladder
------------------
§4.1 requires the **narrowest applicable failure boundary**, which is a
correctness requirement rather than an implementation detail: it decides whether
one bad path kills the plugin or one skill. This module reports containment as a
value (``None`` on failure) and each caller applies its own boundary, which is
the only arrangement that can express the ladder:

===================================  ==========================================
Failing path                         Boundary
===================================  ==========================================
``plugin.json`` outside root         reject the plugin
fixed component location outside     that component **type** is invalid (§6.2)
discovered ``SKILL.md`` outside      that **skill** is skipped (§7.1)
MCP ``command`` / ``cwd`` outside    that **server entry** invalid (§7.2.2)
any other package path               deny access to that path
===================================  ==========================================
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)

# §4.1 rule 4: a config field defined as a plugin-relative path must begin
# with "./". Exposed so the MCP mapper (Increment 2) and the validator agree on
# one spelling of the rule.
PLUGIN_RELATIVE_PREFIX = "./"


def realpath(path: Union[Path, str]) -> Optional[Path]:
    """Canonicalize ``path`` without raising.

    Returns ``None`` when the path cannot be canonicalized at all. ``strict``
    is deliberately off: a path that does not exist yet still has a
    well-defined canonical location, and the validator must be able to reason
    about a missing ``skills/`` without an exception.
    """
    try:
        return Path(os.path.realpath(os.fspath(path), strict=False))
    except (OSError, ValueError, TypeError) as exc:
        # ValueError covers embedded NUL bytes; OSError covers ELOOP on
        # platforms that surface symlink loops as errors rather than
        # returning the unresolved path.
        logger.debug("Could not canonicalize %r: %s", path, exc)
        return None


def is_within(root_real: Path, candidate_real: Path) -> bool:
    """Whether ``candidate_real`` is ``root_real`` or lies beneath it.

    Both arguments must already be canonicalized. The explicit ``os.sep``
    suffix on the prefix comparison is what stops ``/plugins/evil`` from
    counting as inside ``/plugins/ev``.
    """
    root_text = str(root_real)
    candidate_text = str(candidate_real)
    return candidate_text == root_text or candidate_text.startswith(root_text + os.sep)


def resolve_within_root(root: Union[Path, str], candidate: Union[Path, str]) -> Optional[Path]:
    """Canonicalize ``candidate`` and return it only if contained in ``root``.

    Returns ``None`` when the candidate escapes the root or cannot be
    canonicalized. Never raises — the validator that calls this is a total
    function (Requirement 5.1), so a containment check that could throw would
    defeat the point.

    A symlink pointing *within* the root resolves and is accepted; one pointing
    outside is rejected, regardless of the lexical path used to reach it
    (Requirement 7.3).
    """
    root_real = realpath(root)
    if root_real is None:
        return None

    candidate_real = realpath(candidate)
    if candidate_real is None:
        return None

    if not is_within(root_real, candidate_real):
        return None
    return candidate_real


def resolve_relative_within_root(root: Union[Path, str], relative: str) -> Optional[Path]:
    """Resolve a plugin-root-relative path value and enforce containment.

    For §4.1 rule 4 values read out of configuration. ``relative`` is joined
    against the root and then canonicalized, so ``./a/../b`` and ``./b`` agree,
    while ``./../escape`` is rejected.

    An absolute ``relative`` is refused outright rather than silently joined:
    §4.1 defines these fields as plugin-relative, and treating an absolute path
    as relative would quietly change its meaning.
    """
    if not isinstance(relative, str) or not relative:
        return None
    if os.path.isabs(relative):
        return None

    root_real = realpath(root)
    if root_real is None:
        return None
    return resolve_within_root(root_real, root_real / relative)
