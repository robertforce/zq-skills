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
