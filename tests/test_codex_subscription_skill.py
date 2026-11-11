"""验证订阅同步 Skill 的分发完整性与维护副本一致性。"""
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "codex-subscription-sync"


class CodexSubscriptionSkillTests(unittest.TestCase):
    def test_entry_and_ui_metadata_are_included(self):
        entry = (SKILL / "SKILL.md").read_text()
        self.assertTrue(entry.startswith("---\nname: codex-subscription-sync\n"))
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        self.assertNotIn("[TODO:", entry)

    def test_runtime_copies_equal_maintained_packages(self):
        for folder in ("pi", "deepseek-harness"):
            source = ROOT / "scripts" / folder
            expected = [*source.glob("*.mjs"), source / "package.json", source / "package-lock.json"]
            for path in expected:
                with self.subTest(file=f"{folder}/{path.name}"):
                    bundled = SKILL / "scripts" / folder / path.name
                    self.assertTrue(bundled.is_file())
                    self.assertFalse(bundled.is_symlink())
                    self.assertEqual(path.read_bytes(), bundled.read_bytes())

    def test_lockfiles_are_portable_and_direct_dependencies_are_pinned(self):
        for folder in ("pi", "deepseek-harness"):
            package = json.loads((SKILL / "scripts" / folder / "package.json").read_text())
            lock = json.loads((SKILL / "scripts" / folder / "package-lock.json").read_text())
            self.assertEqual(package["dependencies"], lock["packages"][""]["dependencies"])
            for version in package["dependencies"].values():
                self.assertRegex(version, r"^\d+\.\d+\.\d+$")
            self.assertTrue(all(path == "" or path.startswith("node_modules/") for path in lock["packages"]))
            self.assertNotIn("file:", json.dumps(lock))

    def test_documents_resolve_within_the_skill_after_relocation(self):
        self.assertTrue((SKILL / "references" / "pi.md").is_file())
        self.assertTrue((SKILL / "references" / "deepseek-harness.md").is_file())
        for path in SKILL.rglob("*.md"):
            text = path.read_text()
            self.assertNotIn("/Users/zhihu", text)
            self.assertNotIn("/tmp/", text)
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if link.startswith(("https://", "http://", "#")):
                    continue
                linked = (path.parent / link.split("#")[0]).resolve()
                self.assertTrue(linked.is_relative_to(SKILL.resolve()), link)
                self.assertTrue(linked.exists(), link)


if __name__ == "__main__":
    unittest.main()
