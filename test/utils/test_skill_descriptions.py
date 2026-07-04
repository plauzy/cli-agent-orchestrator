"""Tests for skill description quality — validates agentskills.io best practices.

Skills are auto-discovered from both skills/ (user-facing) and
src/cli_agent_orchestrator/skills/ (builtin). Adding a new skill folder
with a valid SKILL.md automatically includes it in these checks — no
manual test updates needed. Symlinked directories are followed.

Checks that all bundled skill SKILL.md files meet quality criteria:
- Descriptions under 1024 characters with imperative phrasing
- Explicit exclusion clauses ("Do NOT use")
- Folder name matches frontmatter name
- Core SKILL.md under 500 lines
"""

from pathlib import Path

import frontmatter
import pytest

# Skill directories to audit (relative to repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]
USER_SKILLS_DIR = REPO_ROOT / "skills"
BUILTIN_SKILLS_DIR = REPO_ROOT / "src" / "cli_agent_orchestrator" / "skills"

# Collect all skill directories (following symlinks)
SKILL_DIRS = []
for parent in [USER_SKILLS_DIR, BUILTIN_SKILLS_DIR]:
    if parent.is_dir():
        for child in sorted(parent.iterdir()):
            skill_md = child / "SKILL.md" if child.is_dir() else None
            # Follow symlinks
            if child.is_symlink():
                resolved = child.resolve()
                skill_md = resolved / "SKILL.md" if resolved.is_dir() else None
            if skill_md and skill_md.exists():
                SKILL_DIRS.append((child.name, skill_md))


def _load_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a SKILL.md file."""
    post = frontmatter.load(str(path))
    return dict(post.metadata)


@pytest.fixture(params=SKILL_DIRS, ids=[name for name, _ in SKILL_DIRS])
def skill(request):
    """Parametrized fixture yielding (folder_name, skill_md_path, frontmatter)."""
    name, path = request.param
    fm = _load_frontmatter(path)
    return name, path, fm


class TestSkillFrontmatter:
    """All skills must have valid frontmatter with name and description."""

    def test_has_name_field(self, skill):
        _, path, fm = skill
        assert "name" in fm, f"{path} missing 'name' in frontmatter"

    def test_has_description_field(self, skill):
        _, path, fm = skill
        assert "description" in fm, f"{path} missing 'description' in frontmatter"

    def test_folder_name_matches_frontmatter_name(self, skill):
        folder_name, path, fm = skill
        assert (
            fm["name"] == folder_name
        ), f"Folder '{folder_name}' doesn't match frontmatter name '{fm['name']}' in {path}"


class TestDescriptionQuality:
    """Descriptions must follow agentskills.io optimization guidelines."""

    def test_under_1024_characters(self, skill):
        _, path, fm = skill
        desc = fm.get("description", "")
        assert len(desc) <= 1024, f"{path}: description is {len(desc)} chars (max 1024)"

    def test_starts_with_imperative_phrasing(self, skill):
        _, path, fm = skill
        desc = fm.get("description", "")
        assert desc.startswith(
            "Use when"
        ), f"{path}: description should start with 'Use when' (got: '{desc[:40]}...')"

    def test_has_exclusion_clause(self, skill):
        _, path, fm = skill
        desc = fm.get("description", "")
        assert (
            "Do NOT use" in desc
        ), f"{path}: description should include 'Do NOT use' exclusion clause"


class TestSkillSize:
    """Skills should follow progressive disclosure — keep core SKILL.md concise."""

    def test_under_500_lines(self, skill):
        _, path, _ = skill
        line_count = len(path.read_text().splitlines())
        assert line_count <= 500, (
            f"{path}: SKILL.md is {line_count} lines (max 500). "
            "Move detailed reference material to references/ subdirectory."
        )
