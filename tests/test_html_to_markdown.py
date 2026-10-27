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
    def test_word_heading_metadata_preserves_levels(self):
        html = '''<p style="mso-style-name: 'Heading 2';mso-outline-level:2">章节</p>
        <p style="mso-outline-level:3"><span>小节</span></p>
        <p style="font-size:16pt;font-weight:bold">1. 普通段落</p>'''
        self.assertEqual(html_to_markdown.convert_html_to_markdown(html),
                         '## 章节\n\n### 小节\n\n1. 普通段落\n')

    def test_word_code_card_preserves_lines_blank_lines_and_style_indents(self):
        html = '''<table><tbody><tr><td><p>示例代码</p>
        <p style="mso-pagination:none;margin-top:0pt;margin-bottom:0pt;margin-left:0pt"><span>export function apply(ctx) {</span></p>
        <p style="mso-pagination:none;margin-top:0pt;margin-bottom:0pt;margin-left:11pt">run(&quot;x&quot;);<br>next();</p>
        <p style="mso-pagination:none;margin-top:0pt;margin-bottom:0pt;margin-left:0pt">&nbsp;</p>
        <p style="mso-pagination:none;margin-top:0pt;margin-bottom:0pt;margin-left:22pt">nested();</p>
        <p style="mso-pagination:none;margin-top:0pt;margin-bottom:0pt;margin-left:0pt">}</p>
        </td></tr></tbody></table>'''
        self.assertEqual(html_to_markdown.convert_html_to_markdown(html),
                         '示例代码\n\n```\nexport function apply(ctx) {\n  run("x");\n  next();\n\n    nested();\n}\n```\n')

    def test_word_directory_card_and_non_code_tables(self):
        line = '<p style="mso-pagination:none;margin-top:0pt;margin-bottom:0pt">{}</p>'
        html = '<table><tr><td><p>目录结构</p>' + line.format('src/') + line.format('├── main.ts') + '</td></tr></table>'
        self.assertEqual(html_to_markdown.convert_html_to_markdown(html),
                         '目录结构\n\n```\nsrc/\n├── main.ts\n```\n')
        for body in (
            '<tr><td><p>重要原则</p>' + line.format('普通说明') + '</td></tr>',
            '<tr><td><p>示例代码</p><p>普通说明</p></td></tr>',
            '<tr><td><p>示例代码</p>' + line.format('x') + '</td><td>其他列</td></tr>',
        ):
            with self.subTest(body=body):
                result = html_to_markdown.convert_html_to_markdown('<table>' + body + '</table>')
                self.assertNotIn('```', result)
                self.assertIn('|', result)

    def test_blockquote_paragraphs_and_nested_quote_keep_markers_with_text(self):
        html = '<blockquote><p>第一段</p><p>第二段<br>下一行</p><blockquote><p>内层</p></blockquote></blockquote><p>正文</p>'
        self.assertEqual(
            html_to_markdown.convert_html_to_markdown(html),
            '> 第一段\n>\n> 第二段\n> 下一行\n>\n> > 内层\n\n正文\n',
        )

    def test_highlighted_code_preserves_newlines_indentation_and_blank_lines(self):
        html = '<pre><code><span>if (ready) {\n</span><span>  run();  \n\n\n</span><span>}\n</span></code></pre>'
        self.assertEqual(
            html_to_markdown.convert_html_to_markdown(html),
            '```\nif (ready) {\n  run();  \n\n\n}\n```\n',
        )

    def test_code_br_and_line_wrappers_preserve_lines(self):
        for body in (
            '<code>a<br>  b<br><br>c</code>',
            '<code><span class="code-snippet__line">a</span><span class="code-snippet__line">  b</span><span class="code-snippet__line"></span><span class="code-snippet__line">c</span></code>',
            '<code><div>a</div><div>  b</div><div></div><div>c</div></code>',
            '<code><span class="code-snippet__line"><span>a</span></span><span class="code-snippet__line"><span>  b</span></span><span class="code-snippet__line"></span><span class="code-snippet__line">c</span></code>',
        ):
            with self.subTest(body=body):
                self.assertEqual(html_to_markdown.convert_html_to_markdown('<pre>' + body + '</pre>'), '```\na\n  b\n\nc\n```\n')

    def test_code_language_uses_explicit_metadata_and_aliases(self):
        for html, language in (
            ('<pre><code class="language-typescript">let x = 1;</code></pre>', 'ts'),
            ('<pre class="lang-python"><code>x = 1</code></pre>', 'python'),
            ('<section class="code-snippet__fix code-snippet__ts"><pre><code>x</code></pre></section>', 'ts'),
            ('<pre data-language="TypeScript"><code>x</code></pre>', 'ts'),
            ('<section class="language-js"><pre><code class="language-ts">x</code></pre></section>', 'ts'),
            ('<pre><code>const x = 1;</code></pre>', ''),
        ):
            with self.subTest(html=html):
                self.assertTrue(html_to_markdown.convert_html_to_markdown(html).startswith('```' + language + '\n'))

    def test_quoted_code_preserves_lines_and_does_not_affect_following_code(self):
        html = '<blockquote><p>代码：</p><pre><code class="language-ts">a\n  b</code></pre></blockquote><pre>single(); other();</pre>'
        self.assertEqual(html_to_markdown.convert_html_to_markdown(html), '> 代码：\n>\n> ```ts\n> a\n>   b\n> ```\n\n```\nsingle(); other();\n```\n')

    def test_code_snippet_style_classes_do_not_declare_a_language(self):
        for name in ('container', 'title', 'toolbar', 'unknown-language'):
            with self.subTest(name=name):
                html = f'<div class="code-snippet__{name}"><pre><code>foo</code></pre></div>'
                self.assertEqual(html_to_markdown.convert_html_to_markdown(html), '```\nfoo\n```\n')

    def test_code_snippet_style_classes_do_not_hide_language_markers(self):
        for attributes, language in (
            ('class="code-snippet__container code-snippet__ts"', 'ts'),
            ('class="code-snippet__title code-snippet__javascript"', 'js'),
            ('class="code-snippet__toolbar code-snippet__python"', 'python'),
            ('class="code-snippet__container language-custom-dsl"', 'custom-dsl'),
            ('class="code-snippet__container lang-custom-dsl"', 'custom-dsl'),
            ('class="code-snippet__container" data-language="custom-dsl"', 'custom-dsl'),
        ):
            with self.subTest(attributes=attributes):
                html = f'<pre {attributes}><code>foo</code></pre>'
                self.assertEqual(html_to_markdown.convert_html_to_markdown(html), f'```{language}\nfoo\n```\n')

    def test_quote_formulas_are_rendered_inside_quote(self):
        html = '<blockquote><p>值<span class="ztext-math" data-tex="x"></span></p><p><span class="ztext-math" data-tex="y=2"></span></p></blockquote>'
        self.assertEqual(html_to_markdown.convert_html_to_markdown(html), '> 值 `$x$`\n>\n> ```math\n> y=2\n> ```\n')

    def test_backticks_inside_code_do_not_close_the_fence(self):
        self.assertEqual(html_to_markdown.convert_html_to_markdown('<pre>```ts\nx\n```</pre>'), '````\n```ts\nx\n```\n````\n')

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
