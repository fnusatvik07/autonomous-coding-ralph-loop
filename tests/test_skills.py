"""Tests for Claude Code skills - verify they exist and have correct frontmatter."""

from pathlib import Path
import yaml


SKILLS_DIR = Path(__file__).parent.parent / ".claude" / "skills"
EXPECTED_SKILLS = ["spec", "code", "qa", "status"]


class TestSkillsExist:
    def test_skills_directory_exists(self):
        assert SKILLS_DIR.exists(), f"Skills directory not found at {SKILLS_DIR}"

    def test_all_skills_present(self):
        for skill in EXPECTED_SKILLS:
            skill_file = SKILLS_DIR / skill / "SKILL.md"
            assert skill_file.exists(), f"Missing skill: {skill}/SKILL.md"


class TestSkillFrontmatter:
    @staticmethod
    def _parse_frontmatter(path: Path) -> dict:
        """Parse YAML frontmatter from a SKILL.md file."""
        content = path.read_text()
        assert content.startswith("---"), f"{path} missing frontmatter"
        end = content.index("---", 3)
        return yaml.safe_load(content[3:end])

    def test_spec_skill(self):
        fm = self._parse_frontmatter(SKILLS_DIR / "spec" / "SKILL.md")
        assert fm["name"] == "spec"
        assert "description" in fm
        assert fm.get("disable-model-invocation") is True
        assert "argument-hint" in fm

    def test_code_skill(self):
        fm = self._parse_frontmatter(SKILLS_DIR / "code" / "SKILL.md")
        assert fm["name"] == "code"
        assert fm.get("disable-model-invocation") is True

    def test_qa_skill(self):
        fm = self._parse_frontmatter(SKILLS_DIR / "qa" / "SKILL.md")
        assert fm["name"] == "qa"
        assert fm.get("disable-model-invocation") is True
        assert fm.get("context") == "fork"
        assert fm.get("agent") == "Explore"

    def test_status_skill(self):
        fm = self._parse_frontmatter(SKILLS_DIR / "status" / "SKILL.md")
        assert fm["name"] == "status"
        # status should be auto-invocable (no disable-model-invocation)
        assert fm.get("disable-model-invocation") is not True


class TestSkillContent:
    def test_skills_have_instructions(self):
        for skill in EXPECTED_SKILLS:
            content = (SKILLS_DIR / skill / "SKILL.md").read_text()
            # After frontmatter, there should be substantial content
            _, body = content.split("---", 2)[1:]
            assert len(body.strip()) > 100, f"{skill} skill body too short"

    def test_spec_references_prd_json(self):
        content = (SKILLS_DIR / "spec" / "SKILL.md").read_text()
        assert "prd.json" in content

    def test_code_references_phases(self):
        content = (SKILLS_DIR / "code" / "SKILL.md").read_text()
        assert "Orient" in content
        assert "Implement" in content
        assert "Verify" in content

    def test_qa_references_verdict(self):
        content = (SKILLS_DIR / "qa" / "SKILL.md").read_text()
        assert "qa_result.json" in content
        assert "passed" in content
