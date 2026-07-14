#!/usr/bin/env python3
"""使用 skill 内置脚本抓取 URL，并将内容保存为 Markdown。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
FETCH_SCRIPT = SCRIPT_DIR / "fetch_html.py"
HTML_TO_MARKDOWN_SCRIPT = SCRIPT_DIR / "html_to_markdown.py"
DEFAULT_OUTPUT_DIR = Path("~/documents/markdown").expanduser()
FETCH_OK_CODES = {0, 2}
UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def url_digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def safe_filename(title: str, fallback: str, max_length: int = 160) -> str:
    name = UNSAFE_FILENAME_CHARS.sub("-", title).strip(" .-\t\r\n")
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = fallback
    if len(name) > max_length:
        name = name[:max_length].rstrip(" .-")
    return name or fallback


def default_cache_dir(output_dir: Path) -> Path:
    return output_dir / ".html-cache"


def metadata_path_for(url: str, cache_dir: Path) -> Path:
    return cache_dir / f"{url_digest(url)}.json"


def build_output_path(url: str, title: str, output_dir: Path) -> Path:
    filename = safe_filename(title, fallback=url_digest(url))
    return output_dir / f"{filename}.md"


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def fetch_html(
    url: str,
    cache_dir: Path,
    timeout: int,
    browser: bool = False,
    headed: bool = False,
    user_data_dir: str = "",
    no_browser_fallback: bool = False,
) -> dict[str, object]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(FETCH_SCRIPT),
        url,
        "--output-dir",
        str(cache_dir),
        "--timeout",
        str(timeout),
    ]
    if browser:
        command.append("--browser")
    if headed:
        command.append("--headed")
    if user_data_dir:
        command.extend(["--user-data-dir", user_data_dir])
    if no_browser_fallback:
        command.append("--no-browser-fallback")

    result = run_command(command)
    if result.returncode not in FETCH_OK_CODES:
        message = result.stderr.strip() or result.stdout.strip() or f"fetch_html.py exited with {result.returncode}"
        raise RuntimeError(message)

    metadata_path = metadata_path_for(url, cache_dir)
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"failed to read fetch metadata {metadata_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid fetch metadata {metadata_path}: {exc}") from exc


def convert_html_to_markdown(html_path: Path, output_path: Path, base_url: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(HTML_TO_MARKDOWN_SCRIPT),
        str(html_path),
        "-o",
        str(output_path),
    ]
    if base_url:
        command.extend(["--base-url", base_url])

    result = run_command(command)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"html_to_markdown.py exited with {result.returncode}"
        raise RuntimeError(message)


def finalize_markdown(output_path: Path, original_url: str) -> None:
    markdown = output_path.read_text(encoding="utf-8").strip()
    final = f"[toc]\n\n{markdown}\n\n原文链接：{original_url}\n"
    output_path.write_text(final, encoding="utf-8")


def save_url_to_markdown(
    url: str,
    output_dir: Path,
    timeout: int,
    strict: bool = False,
    browser: bool = False,
    headed: bool = False,
    user_data_dir: str = "",
    no_browser_fallback: bool = False,
) -> Path:
    output_dir = output_dir.expanduser()
    cache_dir = default_cache_dir(output_dir)
    metadata = fetch_html(
        url,
        cache_dir,
        timeout,
        browser=browser,
        headed=headed,
        user_data_dir=user_data_dir,
        no_browser_fallback=no_browser_fallback,
    )

    if strict and (metadata.get("suspicious") or metadata.get("degraded")):
        reason = metadata.get("degraded_reason") or metadata.get("fallback_reason") or metadata.get("error")
        raise RuntimeError(f"strict mode rejected suspicious fetch result: {reason}")

    html_path_value = str(metadata.get("html_path", ""))
    if not html_path_value:
        raise RuntimeError("抓取元信息中没有 html_path")
    html_path = Path(html_path_value)
    if not html_path.exists():
        raise RuntimeError(f"抓取到的 HTML 文件不存在：{html_path}")

    title = str(metadata.get("title", ""))
    final_url = str(metadata.get("final_url", "")) or url
    output_path = build_output_path(url, title, output_dir)
    convert_html_to_markdown(html_path, output_path, final_url)
    finalize_markdown(output_path, url)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将 URL 内容保存为 Markdown 文件。")
    parser.add_argument("url", help="要保存的目标 URL。")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="输出 .md 文件目录。默认：~/documents/markdown。",
    )
    parser.add_argument("--timeout", type=int, default=30, help="抓取超时时间，单位秒。默认：30。")
    parser.add_argument("--browser", action="store_true", help="强制使用 Playwright 浏览器模式抓取。")
    parser.add_argument("--headed", action="store_true", help="浏览器模式下显示窗口，便于登录或验证。")
    parser.add_argument(
        "--user-data-dir",
        default="",
        help="浏览器模式使用的持久化资料目录；不指定时使用抓取脚本默认值。",
    )
    parser.add_argument(
        "--no-browser-fallback",
        action="store_true",
        help="HTTP 抓取结果可疑时不自动尝试浏览器兜底。",
    )
    parser.add_argument("--strict", action="store_true", help="抓取结果可疑或降级时直接失败。")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output_path = save_url_to_markdown(
            args.url,
            Path(args.output_dir),
            args.timeout,
            strict=args.strict,
            browser=args.browser,
            headed=args.headed,
            user_data_dir=args.user_data_dir,
            no_browser_fallback=args.no_browser_fallback,
        )
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"Markdown 已保存到 {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
