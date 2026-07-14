import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "url-to-markdown" / "scripts" / "url_to_markdown.py"
spec = importlib.util.spec_from_file_location("url_to_markdown_skill", MODULE_PATH)
url_to_markdown = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(url_to_markdown)


class UrlToMarkdownSkillTests(unittest.TestCase):
    def test_default_output_dir_is_lowercase_documents_markdown(self):
        self.assertEqual(
            url_to_markdown.DEFAULT_OUTPUT_DIR,
            Path("~/documents/markdown").expanduser(),
        )

    def test_safe_filename_replaces_unsafe_characters(self):
        filename = url_to_markdown.safe_filename(' A/B:C*D?E"F<G>H| ', fallback="fallback")

        self.assertEqual(filename, "A-B-C-D-E-F-G-H")

    def test_output_path_uses_title_and_fallback_hash(self):
        output_dir = Path("/tmp/out")
        self.assertEqual(
            url_to_markdown.build_output_path("https://example.com/a", "标题", output_dir),
            output_dir / "标题.md",
        )
        self.assertEqual(
            url_to_markdown.build_output_path("https://example.com/a", "", output_dir),
            output_dir / f"{url_to_markdown.url_digest('https://example.com/a')}.md",
        )

    def test_finalize_markdown_adds_toc_and_original_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "page.md"
            output_path.write_text("# Title\n\nBody\n", encoding="utf-8")

            url_to_markdown.finalize_markdown(output_path, "https://example.com/a")

            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "[toc]\n\n# Title\n\nBody\n\n原文链接：https://example.com/a\n",
            )

    def test_save_url_to_markdown_uses_bundled_scripts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            output_dir = tmp / "markdown"
            url = "https://example.com/article"
            cache_dir = output_dir / ".html-cache"
            digest = url_to_markdown.url_digest(url)
            html_path = cache_dir / f"{digest}.html"
            meta_path = cache_dir / f"{digest}.json"

            def fake_run(command):
                self.assertIn(str(url_to_markdown.SCRIPT_DIR), command[1])
                self.assertNotIn(str(ROOT / "scripts"), command[1])
                if command[1].endswith("fetch_html.py"):
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    html_path.write_text("<h1>Hello</h1>", encoding="utf-8")
                    meta_path.write_text(
                        json.dumps(
                            {
                                "title": "Bad/Title?",
                                "html_path": str(html_path),
                                "final_url": "https://example.com/final",
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command[1].endswith("html_to_markdown.py"):
                    output_path = Path(command[command.index("-o") + 1])
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text("# Hello\n", encoding="utf-8")
                    self.assertIn("--base-url", command)
                    self.assertEqual(command[command.index("--base-url") + 1], "https://example.com/final")
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                self.fail(f"unexpected command: {command}")

            with patch.object(url_to_markdown, "run_command", side_effect=fake_run):
                output_path = url_to_markdown.save_url_to_markdown(url, output_dir, timeout=5)

            self.assertEqual(output_path, output_dir / "Bad-Title.md")
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "[toc]\n\n# Hello\n\n原文链接：https://example.com/article\n",
            )

    def test_save_url_to_markdown_can_run_strict_and_pass_browser_options(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            output_dir = tmp / "markdown"
            url = "https://mp.weixin.qq.com/s/restricted"
            cache_dir = output_dir / ".html-cache"
            digest = url_to_markdown.url_digest(url)
            html_path = cache_dir / f"{digest}.html"
            meta_path = cache_dir / f"{digest}.json"

            def fake_run(command):
                if command[1].endswith("fetch_html.py"):
                    self.assertIn("--browser", command)
                    self.assertIn("--headed", command)
                    self.assertIn("--user-data-dir", command)
                    self.assertEqual(command[command.index("--user-data-dir") + 1], "/tmp/profile")
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    html_path.write_text("<h1>Hello</h1>", encoding="utf-8")
                    meta_path.write_text(
                        json.dumps(
                            {
                                "title": "Hello",
                                "html_path": str(html_path),
                                "final_url": url,
                                "suspicious": True,
                                "degraded": True,
                                "degraded_reason": "browser fallback unavailable",
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    return subprocess.CompletedProcess(command, 2, stdout="", stderr="")
                self.fail(f"unexpected command: {command}")

            with patch.object(url_to_markdown, "run_command", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "strict mode"):
                    url_to_markdown.save_url_to_markdown(
                        url,
                        output_dir,
                        timeout=5,
                        strict=True,
                        browser=True,
                        headed=True,
                        user_data_dir="/tmp/profile",
                    )


if __name__ == "__main__":
    unittest.main()
