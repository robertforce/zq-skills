import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.fetch_html import fetch_html


WECHAT_HTML = """<!DOCTYPE html>
<html>
  <head>
    <meta property="og:title" content="30分钟精通 97% 的 Codex" />
    <meta name="author" content="赛博贪吃蛇" />
  </head>
  <body>
    <div id="js_content" class="rich_media_content">
      <p>""" + ("正文内容" * 80) + """</p>
    </div>
  </body>
</html>"""


class FetchHtmlTests(unittest.TestCase):
    def test_build_output_paths_preserves_full_url_identity(self):
        first = fetch_html.build_output_paths(
            "https://mp.weixin.qq.com/s/uNlivBsQtJr7d0EQTh3x_A?scene=334",
            Path("output"),
        )
        second = fetch_html.build_output_paths(
            "https://mp.weixin.qq.com/s/uNlivBsQtJr7d0EQTh3x_A?scene=335",
            Path("output"),
        )

        self.assertNotEqual(first.html_path, second.html_path)
        self.assertEqual(first.html_path.suffix, ".html")
        self.assertEqual(first.meta_path.suffix, ".json")

    def test_analyze_wechat_article_marks_direct_http_result_acceptable(self):
        analysis = fetch_html.analyze_html(
            url="https://mp.weixin.qq.com/s/uNlivBsQtJr7d0EQTh3x_A?scene=334",
            html=WECHAT_HTML,
            status_code=200,
            content_type="text/html; charset=utf-8",
        )

        self.assertEqual(analysis.page_type, "wechat")
        self.assertEqual(analysis.title, "30分钟精通 97% 的 Codex")
        self.assertFalse(analysis.suspicious)
        self.assertEqual(analysis.fallback_reason, "")

    def test_analyze_wechat_restricted_page_requests_fallback(self):
        analysis = fetch_html.analyze_html(
            url="https://mp.weixin.qq.com/s/restricted",
            html="<html><title>环境异常</title><body>请在微信客户端打开</body></html>",
            status_code=200,
            content_type="text/html",
        )

        self.assertTrue(analysis.suspicious)
        self.assertIn("restricted marker", analysis.fallback_reason)

    def test_non_html_response_is_failed_without_saving_html(self):
        response = Mock()
        response.url = "https://example.com/file.pdf"
        response.status_code = 200
        response.headers = {"content-type": "application/pdf"}
        response.text = "%PDF-1.7"

        with patch("scripts.fetch_html.fetch_html.requests.get", return_value=response):
            result = fetch_html.fetch_with_http("https://example.com/file.pdf", timeout=3)

        self.assertFalse(result.ok)
        self.assertIn("non-html response", result.error)

    def test_save_result_writes_html_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = fetch_html.build_output_paths("https://example.com/a", Path(tmpdir))
            analysis = fetch_html.analyze_html(
                url="https://example.com/a",
                html="<html><head><title>Hello</title></head><body>" + ("x" * 250) + "</body></html>",
                status_code=200,
                content_type="text/html",
            )
            metadata = fetch_html.save_result(
                html="<html>Hello</html>",
                paths=paths,
                original_url="https://example.com/a",
                final_url="https://example.com/a",
                method="http",
                status_code=200,
                content_type="text/html",
                analysis=analysis,
                fallback_used=False,
                fallback_reason="",
                error="",
            )

            self.assertEqual(paths.html_path.read_text(encoding="utf-8"), "<html>Hello</html>")
            saved = json.loads(paths.meta_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["title"], "Hello")
            self.assertEqual(saved["method"], "http")
            self.assertEqual(saved["html_path"], str(paths.html_path))
            self.assertEqual(metadata["meta_path"], str(paths.meta_path))

    def test_prepare_html_for_save_makes_wechat_lazy_images_displayable(self):
        raw_html = """<html><head>
<link rel="shortcut icon" href="//res.wx.qq.com/a.ico">
</head><body>
<img class="rich_pages wxw-img" data-src="https://mmbiz.qpic.cn/a.png?wx_fmt=png">
<img class="jump_wx_qrcode_img" src="" data-src="//mmbiz.qpic.cn/qr.png">
</body></html>"""

        processed = fetch_html.prepare_html_for_save(raw_html)

        self.assertIn(
            '<img class="rich_pages wxw-img" data-src="https://mmbiz.qpic.cn/a.png?wx_fmt=png" src="https://mmbiz.qpic.cn/a.png?wx_fmt=png">',
            processed.html,
        )
        self.assertIn('src="https://mmbiz.qpic.cn/qr.png"', processed.html)
        self.assertIn('href="https://res.wx.qq.com/a.ico"', processed.html)
        self.assertEqual(processed.lazy_images_fixed, 2)
        self.assertEqual(processed.protocol_relative_urls_fixed, 2)

    def test_save_result_extracts_wechat_article_and_removes_tail_noise(self):
        html = """<!doctype html>
<html><head><meta property="og:title" content="微信文章"></head><body>
<div id="js_content" class="rich_media_content">
  <p>正文第一段</p>
  <div class="js_pc_qr_code"><p>微信扫一扫关注该公众号</p></div>
  <p>这段是二维码后的噪声</p>
</div>
<div class="recommend_area">相关推荐</div>
</body></html>"""

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = fetch_html.build_output_paths("https://mp.weixin.qq.com/s/a", Path(tmpdir))
            analysis = fetch_html.analyze_html(
                url="https://mp.weixin.qq.com/s/a",
                html=html,
                status_code=200,
                content_type="text/html",
            )

            metadata = fetch_html.save_result(
                html=html,
                paths=paths,
                original_url="https://mp.weixin.qq.com/s/a",
                final_url="https://mp.weixin.qq.com/s/a",
                method="http",
                status_code=200,
                content_type="text/html",
                analysis=analysis,
                fallback_used=False,
                fallback_reason="",
                error="",
            )

            saved_html = paths.html_path.read_text(encoding="utf-8")
            self.assertIn("正文第一段", saved_html)
            self.assertNotIn("微信扫一扫", saved_html)
            self.assertNotIn("二维码后的噪声", saved_html)
            self.assertEqual(metadata["article_extraction"]["strategy"], "wechat:js_content")
            self.assertGreaterEqual(metadata["article_extraction"]["noise_blocks_removed"], 1)

    def test_run_saves_suspicious_http_result_when_browser_fallback_unavailable(self):
        html = """<!doctype html>
<html><head><meta property="og:title" content="受限但可诊断"></head><body>
<div id="js_content" class="rich_media_content">
  <p>请在微信客户端打开</p>
  <p>""" + ("正文内容" * 80) + """</p>
</div>
</body></html>"""

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = fetch_html.build_parser()
            args = parser.parse_args(["https://mp.weixin.qq.com/s/restricted", "--output-dir", tmpdir])
            http_result = fetch_html.FetchResult(
                True,
                html,
                "https://mp.weixin.qq.com/s/restricted",
                200,
                "text/html",
            )
            browser_result = fetch_html.FetchResult(
                False,
                "",
                "https://mp.weixin.qq.com/s/restricted",
                None,
                "",
                "browser fallback requires playwright",
            )

            with patch("scripts.fetch_html.fetch_html.fetch_with_http", return_value=http_result):
                with patch("scripts.fetch_html.fetch_html.fetch_with_browser", return_value=browser_result):
                    code = fetch_html.run(args)

            paths = fetch_html.build_output_paths("https://mp.weixin.qq.com/s/restricted", Path(tmpdir))
            metadata = json.loads(paths.meta_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 2)
            self.assertTrue(paths.html_path.exists())
            self.assertEqual(metadata["html_path"], str(paths.html_path))
            self.assertTrue(metadata["degraded"])
            self.assertIn("browser fallback requires playwright", metadata["degraded_reason"])


if __name__ == "__main__":
    unittest.main()
