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
    def test_skill_documents_formula_and_zhida_link_output_rules(self):
        skill_text = (ROOT / "skills" / "url-to-markdown" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("最外层再使用反引号", skill_text)
        self.assertIn("只保留链接文字", skill_text)

    def test_bundled_html_converter_matches_project_copy(self):
        project_copy = ROOT / "scripts" / "html_to_markdown" / "html_to_markdown.py"
        bundled_copy = ROOT / "skills" / "url-to-markdown" / "scripts" / "html_to_markdown.py"

        self.assertEqual(project_copy.read_bytes(), bundled_copy.read_bytes())

    def test_default_output_dir_is_lowercase_documents_markdown(self):
        self.assertEqual(
            url_to_markdown.DEFAULT_OUTPUT_DIR,
            Path("~/documents/markdown").expanduser(),
        )

    def test_default_browser_profile_is_dedicated_and_persistent(self):
        self.assertEqual(
            url_to_markdown.DEFAULT_BROWSER_PROFILE,
            Path("~/.url-to-markdown/chrome-profile").expanduser(),
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

    def test_suspicious_zhihu_fetch_is_rejected_with_existing_chrome_recovery_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "markdown"
            cache_dir = output_dir / ".html-cache"
            url = "https://zhuanlan.zhihu.com/p/1984387073625593089"
            meta_path = cache_dir / f"{url_to_markdown.url_digest(url)}.json"

            def fake_run(command):
                cache_dir.mkdir(parents=True, exist_ok=True)
                meta_path.write_text(
                    json.dumps(
                        {
                            "title": "",
                            "html_path": "",
                            "final_url": url,
                            "page_type": "zhihu",
                            "suspicious": True,
                            "fallback_reason": "status 403, missing zhihu article structure",
                            "error": "",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 2, stdout="", stderr="")

            with patch.object(url_to_markdown, "run_command", side_effect=fake_run):
                with self.assertRaises(RuntimeError) as raised:
                    url_to_markdown.save_url_to_markdown(url, output_dir, timeout=5)

            message = str(raised.exception)
            self.assertIn("--existing-chrome", message)
            self.assertIn("authenticated-chrome", message)
            self.assertIn(url, message)

    def test_existing_chrome_option_is_forwarded_to_bundled_fetcher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "markdown"
            cache_dir = output_dir / ".html-cache"
            url = "https://example.com/private"
            meta_path = cache_dir / f"{url_to_markdown.url_digest(url)}.json"

            def fake_run(command):
                if command[1].endswith("fetch_html.py"):
                    self.assertIn("--existing-chrome", command)
                    self.assertEqual(
                        command[command.index("--browser-name") + 1],
                        "authenticated-chrome",
                    )
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    meta_path.write_text(
                        json.dumps(
                            {
                                "title": "Private",
                                "html_path": str(cache_dir / "page.html"),
                                "final_url": url,
                                "suspicious": False,
                            }
                        ),
                        encoding="utf-8",
                    )
                    (cache_dir / "page.html").write_text("<h1>Private</h1>", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command[1].endswith("html_to_markdown.py"):
                    output_path = Path(command[command.index("-o") + 1])
                    output_path.write_text("# Private\n", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                self.fail(f"unexpected command: {command}")

            with patch.object(url_to_markdown, "run_command", side_effect=fake_run):
                output_path = url_to_markdown.save_url_to_markdown(
                    url,
                    output_dir,
                    timeout=5,
                    existing_chrome=True,
                    browser_name="authenticated-chrome",
                )

            self.assertEqual(output_path.read_text(encoding="utf-8").splitlines()[0], "[toc]")

    def test_failed_fetch_does_not_reuse_stale_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / ".html-cache"
            cache_dir.mkdir(parents=True)
            url = "https://example.com/stale"
            url_to_markdown.metadata_path_for(url, cache_dir).write_text(
                json.dumps({"title": "旧结果", "html_path": "/tmp/stale.html"}),
                encoding="utf-8",
            )

            failed = subprocess.CompletedProcess(
                ["fetch_html.py"],
                1,
                stdout="",
                stderr="本次抓取进程崩溃",
            )
            with patch.object(url_to_markdown, "run_command", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "本次抓取进程崩溃"):
                    url_to_markdown.fetch_html(url, cache_dir, timeout=5)

    def test_generic_page_without_article_container_is_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "markdown"
            cache_dir = output_dir / ".html-cache"
            url = "https://example.com/page-shell"
            meta_path = cache_dir / f"{url_to_markdown.url_digest(url)}.json"
            html_path = cache_dir / "page.html"

            def fake_run(command):
                self.assertTrue(command[1].endswith("fetch_html.py"))
                cache_dir.mkdir(parents=True, exist_ok=True)
                html_path.write_text("", encoding="utf-8")
                meta_path.write_text(
                    json.dumps(
                        {
                            "title": "页面外壳",
                            "html_path": str(html_path),
                            "final_url": url,
                            "page_type": "generic",
                            "suspicious": True,
                            "fallback_reason": "missing generic article structure",
                            "article_extraction": {
                                "used": False,
                                "strategy": "generic:not_found",
                                "reason": "semantic article container not found",
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 2, stdout="", stderr="")

            with patch.object(url_to_markdown, "run_command", side_effect=fake_run) as run:
                with self.assertRaisesRegex(RuntimeError, "未检测到可归档的文章正文"):
                    url_to_markdown.save_url_to_markdown(url, output_dir, timeout=5)

            self.assertEqual(run.call_count, 1)
            self.assertFalse((output_dir / "页面外壳.md").exists())


if __name__ == "__main__":
    unittest.main()
