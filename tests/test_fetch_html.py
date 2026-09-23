import json
import subprocess
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

ZHIHU_ARTICLE_HTML = """<!doctype html>
<html><head>
<title>(99+ 封私信 / 29 条消息) 强化学习入门 - 知乎</title>
<meta property="og:title" content="(99+ 封私信 / 29 条消息) 强化学习入门 - 知乎">
<meta data-react-helmet="true" content="强化学习入门" itemprop="headline" data-extra="1">
</head><body>
<header>知乎导航</header>
<article>
  <h1>强化学习入门</h1>
  <div class="Post-RichText"><p>这是知乎文章正文。</p><pre><code>loss.backward()</code></pre></div>
</article>
<aside>相关推荐</aside>
<section>评论区</section>
</body></html>"""

ZHIHU_CHALLENGE_HTML = """<!doctype html><html><head>
<meta id="zh-zse-ck" content="abcd">
</head><body>知乎，让每一次点击都充满意义<script src="https://static.zhihu.com/zse-ck/v4/index.js"></script></body></html>"""


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
        response.geturl.return_value = "https://example.com/file.pdf"
        response.status = 200
        response.headers = Mock()
        response.headers.get.side_effect = lambda key, default="": {
            "content-type": "application/pdf",
        }.get(key.lower(), default)
        response.headers.get_content_charset.return_value = None
        response.read.return_value = b"%PDF-1.7"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch("scripts.fetch_html.fetch_html.request.urlopen", return_value=response):
            result = fetch_html.fetch_with_http("https://example.com/file.pdf", timeout=3)

        self.assertFalse(result.ok)
        self.assertIn("non-html response", result.error)

    def test_analyze_zhihu_challenge_page_requests_login_fallback(self):
        analysis = fetch_html.analyze_html(
            url="https://zhuanlan.zhihu.com/p/1984387073625593089",
            html=ZHIHU_CHALLENGE_HTML,
            status_code=403,
            content_type="text/html; charset=utf-8",
        )

        self.assertTrue(analysis.suspicious)
        self.assertIn("status 403", analysis.fallback_reason)
        self.assertIn("missing zhihu article structure", analysis.fallback_reason)

    def test_zhihu_script_text_does_not_count_as_article_structure(self):
        html = "<html><head><title>验证</title></head><body><script>const className = 'ztext';</script></body></html>"

        analysis = fetch_html.analyze_html(
            url="https://zhuanlan.zhihu.com/p/1",
            html=html,
            status_code=200,
            content_type="text/html",
        )

        self.assertTrue(analysis.suspicious)
        self.assertIn("missing zhihu article structure", analysis.fallback_reason)

    def test_empty_zhihu_article_container_is_suspicious(self):
        html = "<html><head><title>空文章</title></head><body>" + ("页面外壳" * 80) + '<div class="Post-RichText"></div></body></html>'

        analysis = fetch_html.analyze_html(
            url="https://zhuanlan.zhihu.com/p/1",
            html=html,
            status_code=200,
            content_type="text/html",
        )

        self.assertTrue(analysis.suspicious)
        self.assertIn("short zhihu article body", analysis.fallback_reason)

    def test_extract_zhihu_article_excludes_page_shell(self):
        extraction = fetch_html.extract_article_html("zhihu", ZHIHU_ARTICLE_HTML)

        self.assertTrue(extraction.used)
        self.assertEqual(extraction.strategy, "zhihu:post-richtext")
        self.assertIn("这是知乎文章正文", extraction.html)
        self.assertIn("loss.backward()", extraction.html)
        self.assertNotIn("知乎导航", extraction.html)
        self.assertNotIn("相关推荐", extraction.html)
        self.assertNotIn("评论区", extraction.html)

    def test_extract_title_prefers_article_headline_over_notification_decorated_page_title(self):
        self.assertEqual(fetch_html.extract_title(ZHIHU_ARTICLE_HTML), "强化学习入门")

    def test_default_browser_profile_is_dedicated_and_persistent(self):
        args = fetch_html.build_parser().parse_args(["https://example.com/article"])

        self.assertEqual(
            Path(args.user_data_dir),
            Path("~/.url-to-markdown/chrome-profile").expanduser(),
        )

    def test_existing_chrome_fetch_reuses_named_authenticated_browser(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            if command[-2:] == ["browser", "list"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout='id=direct_local_1 name="authenticated-chrome" type=chrome-direct\n',
                    stderr="",
                )
            if "open" in command:
                return subprocess.CompletedProcess(command, 0, stdout="opened", stderr="")
            if command[-2:] == ["wait", "stable"]:
                return subprocess.CompletedProcess(command, 0, stdout="stable", stderr="")
            if "selector" in command and "wait" in command:
                return subprocess.CompletedProcess(command, 0, stdout="attached", stderr="")
            if command[-2:] == ["get", "html"]:
                return subprocess.CompletedProcess(command, 0, stdout=ZHIHU_ARTICLE_HTML, stderr="")
            if command[-3:] == ["session", "close", command[-1]]:
                raise subprocess.TimeoutExpired(command, 30)
            self.fail(f"unexpected command: {command}")

        with patch("scripts.fetch_html.fetch_html.shutil.which", return_value="/usr/local/bin/browser-act"):
            with patch("scripts.fetch_html.fetch_html.subprocess.run", side_effect=fake_run):
                result = fetch_html.fetch_with_existing_chrome(
                    "https://zhuanlan.zhihu.com/p/1984387073625593089",
                    timeout=30,
                    browser_name="authenticated-chrome",
                )

        self.assertTrue(result.ok)
        self.assertIn("这是知乎文章正文", result.html)
        self.assertTrue(any("direct_local_1" in command and "open" in command for command in commands))
        self.assertTrue(any(command[-2:] == ["wait", "stable"] for command in commands))
        self.assertTrue(any(command[1:3] == ["session", "close"] for command in commands))

    def test_extract_generic_semantic_article_excludes_page_shell(self):
        html = "<html><head><title>文章</title></head><body><nav>导航</nav><article><h1>文章</h1><p>正文</p></article><aside>推荐</aside></body></html>"

        extraction = fetch_html.extract_article_html("generic", html)

        self.assertTrue(extraction.used)
        self.assertEqual(extraction.strategy, "generic:article")
        self.assertIn("正文", extraction.html)
        self.assertNotIn("导航", extraction.html)
        self.assertNotIn("推荐", extraction.html)

    def test_extract_generic_common_content_container_excludes_page_shell(self):
        html = '<html><head><title>文章</title></head><body><nav>导航</nav><div id="article-content"><p>正文内容</p></div><aside>推荐</aside></body></html>'

        extraction = fetch_html.extract_article_html("generic", html)

        self.assertTrue(extraction.used)
        self.assertEqual(extraction.strategy, "generic:id:article-content")
        self.assertIn("正文内容", extraction.html)
        self.assertNotIn("导航", extraction.html)

    def test_generic_page_without_article_container_is_suspicious(self):
        html = "<html><head><title>页面</title></head><body><nav>导航</nav><div>" + ("页面外壳" * 80) + "</div></body></html>"

        analysis = fetch_html.analyze_html(
            url="https://example.com/page",
            html=html,
            status_code=200,
            content_type="text/html",
        )

        self.assertTrue(analysis.suspicious)
        self.assertIn("missing generic article structure", analysis.fallback_reason)

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
                html="<article>Hello</article>",
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

            self.assertEqual(paths.html_path.read_text(encoding="utf-8"), "<article>Hello</article>")
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
