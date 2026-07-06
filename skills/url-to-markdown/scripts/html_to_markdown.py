#!/usr/bin/env python3
"""Convert a local HTML file to Markdown."""

from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin


BLOCK_TAGS = {
    "article",
    "aside",
    "body",
    "div",
    "footer",
    "header",
    "main",
    "nav",
    "section",
}

SKIP_TAGS = {"head", "script", "style", "noscript", "template"}


class MarkdownConverter(HTMLParser):
    """Small HTML-to-Markdown converter for common article markup."""

    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: List[str] = []
        self.skip_stack: List[str] = []
        self.inline_stack: List[str] = []
        self.link_stack: List[str] = []
        self.list_stack: List[dict[str, int | str]] = []
        self.in_pre = False
        self.in_code = False
        self.table_rows: Optional[List[List[str]]] = None
        self.current_row: Optional[List[str]] = None
        self.current_cell: Optional[List[str]] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value or "" for name, value in attrs}

        if tag in SKIP_TAGS:
            self.skip_stack.append(tag)
            return
        if self.skip_stack:
            return

        if self.table_rows is not None:
            self._handle_table_start(tag)
            return

        if tag == "table":
            self._blank_line()
            self.table_rows = []
            return
        if tag in BLOCK_TAGS or tag in {"p", "figure", "figcaption"}:
            self._blank_line()
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._blank_line()
            self._append("#" * int(tag[1]) + " ")
        elif tag == "blockquote":
            self._blank_line()
            self._append("> ")
        elif tag in {"ul", "ol"}:
            self._blank_line()
            self.list_stack.append({"type": tag, "index": 1})
        elif tag == "li":
            self._start_list_item()
        elif tag == "br":
            self._append("\n")
        elif tag == "hr":
            self._blank_line()
            self._append("---")
            self._blank_line()
        elif tag in {"strong", "b"}:
            self._append("**")
            self.inline_stack.append("**")
        elif tag in {"em", "i"}:
            self._append("*")
            self.inline_stack.append("*")
        elif tag == "code":
            if not self.in_pre:
                self._append("`")
            self.in_code = True
        elif tag == "pre":
            self._blank_line()
            self._append("```\n")
            self.in_pre = True
        elif tag == "a":
            href = self._resolve_url(attributes.get("href", ""))
            self.link_stack.append(href)
            self._append("[")
        elif tag == "img":
            src = self._resolve_url(attributes.get("src", ""))
            alt = self._clean_inline(attributes.get("alt", ""))
            if src:
                self._append(f"![{alt}]({src})")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return

        if self.table_rows is not None:
            self._handle_table_end(tag)
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "figure", "figcaption"}:
            self._blank_line()
        elif tag in BLOCK_TAGS:
            self._blank_line()
        elif tag in {"ul", "ol"}:
            if self.list_stack:
                self.list_stack.pop()
            self._blank_line()
        elif tag in {"strong", "b", "em", "i"} and self.inline_stack:
            self._append(self.inline_stack.pop())
        elif tag == "code":
            if self.in_code and not self.in_pre:
                self._append("`")
            self.in_code = False
        elif tag == "pre":
            self._append("\n```")
            self.in_pre = False
            self._blank_line()
        elif tag == "a":
            href = self.link_stack.pop() if self.link_stack else ""
            self._append(f"]({href})" if href else "]")

    def handle_data(self, data: str) -> None:
        if self.skip_stack:
            return
        if self.current_cell is not None:
            self.current_cell.append(data)
            return
        if self.in_pre:
            self._append(data.rstrip("\n"))
            return
        text = self._normalize_inline(data)
        if text.strip():
            self._append_text(text)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(unescape(f"&#{name};"))

    def markdown(self) -> str:
        output = "".join(self.parts)
        output = re.sub(r"[ \t]+\n", "\n", output)
        output = re.sub(r"\n{3,}", "\n\n", output)
        return output.strip() + "\n"

    def _handle_table_start(self, tag: str) -> None:
        if tag == "tr":
            self.current_row = []
        elif tag in {"td", "th"}:
            self.current_cell = []
        elif tag == "br" and self.current_cell is not None:
            self.current_cell.append(" ")

    def _handle_table_end(self, tag: str) -> None:
        if tag in {"td", "th"} and self.current_row is not None and self.current_cell is not None:
            self.current_row.append(self._clean_inline(" ".join(self.current_cell)))
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if any(cell for cell in self.current_row):
                self.table_rows.append(self.current_row)
            self.current_row = None
        elif tag == "table":
            rows = self.table_rows or []
            self.table_rows = None
            self._append_table(rows)
            self._blank_line()

    def _append_table(self, rows: List[List[str]]) -> None:
        if not rows:
            return
        width = max(len(row) for row in rows)
        normalized = [row + [""] * (width - len(row)) for row in rows]
        self._append("| " + " | ".join(self._escape_table_cell(cell) for cell in normalized[0]) + " |\n")
        self._append("| " + " | ".join("---" for _ in range(width)) + " |\n")
        for row in normalized[1:]:
            self._append("| " + " | ".join(self._escape_table_cell(cell) for cell in row) + " |\n")

    def _start_list_item(self) -> None:
        depth = max(len(self.list_stack) - 1, 0)
        marker = "- "
        if self.list_stack and self.list_stack[-1]["type"] == "ol":
            index = int(self.list_stack[-1]["index"])
            marker = f"{index}. "
            self.list_stack[-1]["index"] = index + 1
        self._append("\n" + ("  " * depth) + marker)

    def _blank_line(self) -> None:
        current = "".join(self.parts)
        if not current or current.endswith("\n\n"):
            return
        if current.endswith("\n"):
            self._append("\n")
        else:
            self._append("\n\n")

    def _append_text(self, text: str) -> None:
        if not self.parts:
            self._append(text.lstrip())
            return
        previous = self.parts[-1]
        if previous.endswith(("\n", "[", "(")):
            text = text.lstrip()
        self._append(text)

    def _append(self, text: str) -> None:
        self.parts.append(text)

    def _resolve_url(self, url: str) -> str:
        if self.base_url and url:
            return urljoin(self.base_url, url)
        return url

    @staticmethod
    def _clean_inline(text: str) -> str:
        return re.sub(r"\s+", " ", unescape(text)).strip()

    @staticmethod
    def _normalize_inline(text: str) -> str:
        return re.sub(r"\s+", " ", unescape(text))

    @staticmethod
    def _escape_table_cell(text: str) -> str:
        return text.replace("|", r"\|")


def convert_html_to_markdown(html: str, base_url: str = "") -> str:
    converter = MarkdownConverter(base_url=base_url)
    converter.feed(html)
    converter.close()
    return converter.markdown()


def default_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".md")


def run(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else default_output_path(input_path)

    try:
        html = input_path.read_text(encoding=args.encoding)
    except OSError as exc:
        print(f"ERROR: failed to read {input_path}: {exc}", file=sys.stderr)
        return 1

    markdown = convert_html_to_markdown(html, base_url=args.base_url)

    if args.stdout:
        sys.stdout.write(markdown)
        return 0

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to write {output_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Markdown saved to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a local HTML file to Markdown.")
    parser.add_argument("input", help="Path to the source .html file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the target .md file. Defaults to the input path with a .md suffix.",
    )
    parser.add_argument("--encoding", default="utf-8", help="Input file encoding. Default: utf-8.")
    parser.add_argument("--base-url", default="", help="Resolve relative links and images against this URL.")
    parser.add_argument("--stdout", action="store_true", help="Print Markdown instead of writing a file.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
