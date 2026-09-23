import tempfile
import unittest
from pathlib import Path

from scripts.html_to_markdown import html_to_markdown


ARTICLE_HTML = """<!doctype html>
<html>
  <head>
    <title>Ignored title</title>
    <style>body { color: red; }</style>
  </head>
  <body>
    <article>
      <h1>Hello HTML</h1>
      <p>This is <strong>important</strong> and <em>useful</em>.</p>
      <p>Visit <a href="/docs">the docs</a>.</p>
      <img src="/cover.png" alt="Cover">
      <ul>
        <li>First</li>
        <li>Second</li>
      </ul>
      <pre><code>print("hi")</code></pre>
      <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>A</td><td>1</td></tr>
      </table>
    </article>
  </body>
</html>"""


class HtmlToMarkdownTests(unittest.TestCase):
    def test_convert_common_article_markup(self):
        markdown = html_to_markdown.convert_html_to_markdown(
            ARTICLE_HTML,
            base_url="https://example.com/base/",
        )

        self.assertIn("# Hello HTML", markdown)
        self.assertIn("This is **important** and *useful*.", markdown)
        self.assertIn("[the docs](https://example.com/docs)", markdown)
        self.assertIn("![Cover](https://example.com/cover.png)", markdown)
        self.assertIn("- First", markdown)
        self.assertIn("- Second", markdown)
        self.assertIn('```\nprint("hi")\n```', markdown)
        self.assertIn("| Name | Value |", markdown)
        self.assertIn("| --- | --- |", markdown)
        self.assertIn("| A | 1 |", markdown)
        self.assertNotIn("color: red", markdown)

    def test_list_marker_stays_with_text_inside_block_children(self):
        html = """
        <ol>
          <li><p>第一项</p></li>
          <li><div><span>第二项</span></div></li>
        </ol>
        <ul>
          <li><section><p>第三项</p></section></li>
        </ul>
        """

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertIn("1. 第一项", markdown)
        self.assertIn("2. 第二项", markdown)
        self.assertIn("- 第三项", markdown)
        self.assertNotRegex(markdown, r"(?m)^\s*(?:[-*+]|\d+\.)\s*$")

    def test_wechat_code_line_index_list_is_ignored(self):
        html = """
        <section class="code-snippet__fix code-snippet__js">
          <ul class="code-snippet__line-index code-snippet__js">
            <li></li><li></li>
          </ul>
          <pre><code>uv tool install browser-act-cli
browser-act get-skills core</code></pre>
        </section>
        """

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertIn("uv tool install browser-act-cli", markdown)
        self.assertIn("browser-act get-skills core", markdown)
        self.assertNotRegex(markdown, r"(?m)^\s*(?:[-*+]|\d+\.)\s*$")

    def test_zhihu_inline_formula_uses_dollar_delimiters(self):
        html = r"""
        <p>其中 <span class="ztext-math" data-tex="r_t(\theta)">
          <span class="MathJax_SVG">rendered formula</span>
        </span> 表示新旧策略的概率比。</p>
        """

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertIn(r"其中 `$r_t(\theta)$` 表示新旧策略的概率比。", markdown)
        self.assertNotIn(r"$$r_t(\theta)$$", markdown)
        self.assertNotIn("rendered formula", markdown)

    def test_inline_formula_is_separated_from_preceding_text(self):
        html = '<p>不是<span class="ztext-math" data-tex="x=5"></span>，而是别的值。</p>'

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertEqual(markdown, "不是 `$x=5$`，而是别的值。\n")

    def test_zhida_search_link_keeps_only_label_text(self):
        html = """
        <p>模型（<a href="https://zhida.zhihu.com/search?q=DeepSeek-R1">DeepSeek-R1</a>）
        使用<a href="https://example.com/docs">普通链接</a>。</p>
        """

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertIn("模型（DeepSeek-R1）", markdown)
        self.assertNotIn("zhida.zhihu.com/search", markdown)
        self.assertNotIn("[DeepSeek-R1]", markdown)
        self.assertIn("[普通链接](https://example.com/docs)", markdown)

    def test_zhihu_standalone_formula_uses_math_fence(self):
        html = r"""
        <p><span class="ztext-math" data-tex=" \begin{align*} L(\theta) = \mathbb{E}[r] \end{align*} ">
          <span class="MathJax_Preview">preview</span>
          <span class="MathJax_SVG">rendered formula</span>
        </span></p>
        """

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertIn(
            "```math\n" + r"\begin{align*} L(\theta) = \mathbb{E}[r] \end{align*}" + "\n```",
            markdown,
        )
        self.assertNotIn("preview", markdown)
        self.assertNotIn("rendered formula", markdown)

    def test_formula_pipe_is_escaped_inside_markdown_table(self):
        html = r"""
        <table>
          <tr><th>公式</th><th>说明</th></tr>
          <tr><td><span class="ztext-math" data-tex="a|b"><span>rendered</span></span></td><td>条件</td></tr>
        </table>
        """

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertIn(r"| `$a\|b$` | 条件 |", markdown)
        self.assertNotIn("rendered", markdown)

    def test_empty_formula_attribute_does_not_leak_mathjax_text(self):
        html = '<p>A<span class="ztext-math" data-tex="  "><span>rendered formula</span></span>B</p>'

        markdown = html_to_markdown.convert_html_to_markdown(html)

        self.assertEqual(markdown, "AB\n")
        self.assertNotIn("rendered formula", markdown)

    def test_default_output_path_replaces_suffix(self):
        self.assertEqual(
            html_to_markdown.default_output_path(Path("page.html")),
            Path("page.md"),
        )

    def test_run_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "page.html"
            output_path = Path(tmpdir) / "out.md"
            input_path.write_text("<h1>Title</h1><p>Hello</p>", encoding="utf-8")

            code = html_to_markdown.main([str(input_path), "-o", str(output_path)])

            self.assertEqual(code, 0)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "# Title\n\nHello\n")


if __name__ == "__main__":
    unittest.main()
