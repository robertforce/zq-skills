#!/usr/bin/env python3
"""Fetch a web page's HTML source and save it with diagnostic metadata."""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib import error, request
from urllib.parse import urlparse

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_BROWSER_PROFILE = Path("~/.url-to-markdown/chrome-profile").expanduser()
DEFAULT_LOGIN_TIMEOUT = 300
DEFAULT_EXISTING_CHROME_NAME = "authenticated-chrome"

RESTRICTED_MARKERS = (
    "请在微信客户端打开",
    "环境异常",
    "访问受限",
    "请输入验证码",
    "拖动滑块",
    "完成验证",
    "登录后查看",
    "登录后继续",
    "login_required",
    "安全验证",
    "captcha",
    "forbidden",
)


@dataclass(frozen=True)
class OutputPaths:
    html_path: Path
    raw_html_path: Path
    meta_path: Path


@dataclass(frozen=True)
class HtmlAnalysis:
    page_type: str
    title: str
    suspicious: bool
    fallback_reason: str
    has_html_shell: bool
    body_length: int


@dataclass(frozen=True)
class FetchResult:
    ok: bool
    html: str
    final_url: str
    status_code: Optional[int]
    content_type: str
    error: str = ""


@dataclass(frozen=True)
class HtmlSavePreparation:
    html: str
    lazy_images_fixed: int
    protocol_relative_urls_fixed: int


@dataclass(frozen=True)
class ArticleExtraction:
    html: str
    strategy: str
    used: bool
    noise_blocks_removed: int
    reason: str = ""


def build_output_paths(url: str, output_dir: Path) -> OutputPaths:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return OutputPaths(
        html_path=output_dir / f"{digest}.html",
        raw_html_path=output_dir / f"{digest}.raw.html",
        meta_path=output_dir / f"{digest}.json",
    )


def detect_page_type(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    if hostname == "mp.weixin.qq.com":
        return "wechat"
    if hostname == "zhihu.com" or hostname.endswith(".zhihu.com"):
        return "zhihu"
    return "generic"


def extract_title(html: str) -> str:
    meta_tags = re.findall(r"<meta\b[^>]*>", html, flags=re.IGNORECASE | re.DOTALL)
    for identity_name, identity_value in (("itemprop", "headline"), ("property", "og:title")):
        for tag in meta_tags:
            attrs = _parse_tag_attributes(tag)
            if attrs.get(identity_name, "").lower() == identity_value and attrs.get("content"):
                return re.sub(r"\s+", " ", attrs["content"]).strip()

    for pattern in (
        r'<h1\b[^>]*class=["\'][^"\']*\bPost-Title\b[^"\']*["\'][^>]*>(.*?)</h1>',
        r"<title[^>]*>(.*?)</title>",
    ):
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return html_lib.unescape(re.sub(r"\s+", " ", match.group(1)).strip())
    return ""


def _parse_tag_attributes(tag: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    pattern = re.compile(r"([^\s=/>]+)\s*=\s*(?:([\"'])(.*?)\2|([^\s>]+))", re.DOTALL)
    for match in pattern.finditer(tag):
        attrs[match.group(1).lower()] = html_lib.unescape(match.group(3) or match.group(4) or "")
    return attrs


def _strip_markup(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return html_lib.unescape(re.sub(r"\s+", " ", text)).strip()


def _has_wechat_article_structure(html: str) -> bool:
    lowered = html.lower()
    return "js_content" in lowered or "rich_media_content" in lowered


def _has_zhihu_article_structure(html: str) -> bool:
    for tag in re.findall(r"<[a-zA-Z][\w:-]*\b[^>]*>", html, flags=re.DOTALL):
        classes = set(_parse_tag_attributes(tag).get("class", "").lower().split())
        if classes.intersection({"post-richtext", "richcontent-inner"}):
            return True
        if "richtext" in classes and "ztext" in classes:
            return True
    return False


def analyze_html(url: str, html: str, status_code: Optional[int], content_type: str) -> HtmlAnalysis:
    page_type = detect_page_type(url)
    title = extract_title(html)
    text = _strip_markup(html)
    lowered_text = text.lower()
    lowered_html = html.lower()
    has_html_shell = "<html" in lowered_html or "<!doctype html" in lowered_html
    reasons = []

    if status_code in (401, 403, 407, 418, 429):
        reasons.append(f"status {status_code}")
    if not has_html_shell:
        reasons.append("missing html shell")
    if not title:
        reasons.append("missing title")
    if len(text) < 120:
        reasons.append("short body")
    if any(marker.lower() in lowered_text for marker in RESTRICTED_MARKERS):
        reasons.append("restricted marker")
    if page_type == "wechat" and not _has_wechat_article_structure(html):
        reasons.append("missing wechat article structure")
    if page_type == "zhihu":
        extraction = extract_article_html(page_type, html)
        if not extraction.used:
            reasons.append("missing zhihu article structure")
        elif len(_strip_markup(extraction.html)) < 120:
            reasons.append("short zhihu article body")
    if page_type == "generic" and not extract_article_html(page_type, html).used:
        reasons.append("missing generic article structure")

    return HtmlAnalysis(
        page_type=page_type,
        title=title,
        suspicious=bool(reasons),
        fallback_reason=", ".join(reasons),
        has_html_shell=has_html_shell,
        body_length=len(text),
    )


def _looks_like_html(content_type: str, text: str) -> bool:
    lowered_type = content_type.lower()
    lowered_text = text.lstrip().lower()
    return (
        "text/html" in lowered_type
        or "application/xhtml" in lowered_type
        or lowered_text.startswith("<!doctype html")
        or lowered_text.startswith("<html")
    )


def fetch_with_http(url: str, timeout: int) -> FetchResult:
    http_request = request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        response = request.urlopen(http_request, timeout=timeout)
    except error.HTTPError as exc:
        response = exc
    except (error.URLError, TimeoutError, OSError) as exc:
        return FetchResult(False, "", url, None, "", f"network error: {exc}")

    try:
        body = response.read()
        content_type = response.headers.get("content-type", "")
        charset = response.headers.get_content_charset()
        if not charset:
            charset_match = re.search(br'<meta\b[^>]*charset\s*=\s*["\']?([\w.-]+)', body[:8192], re.IGNORECASE)
            charset = charset_match.group(1).decode("ascii", errors="ignore") if charset_match else "utf-8"
        try:
            text = body.decode(charset, errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        final_url = response.geturl()
        status_code = getattr(response, "status", None) or getattr(response, "code", None)
    except (OSError, TimeoutError, http.client.IncompleteRead) as exc:
        return FetchResult(False, "", url, None, "", f"network error while reading response: {exc}")
    finally:
        response.close()

    if not _looks_like_html(content_type, text):
        return FetchResult(
            False,
            "",
            final_url,
            status_code,
            content_type,
            f"non-html response: {content_type or 'unknown content type'}",
        )

    return FetchResult(True, text, final_url, status_code, content_type)


def _browser_act_error(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or f"browser-act exited with {result.returncode}"


def _resolve_browser_act_id(browser_name: str, timeout: int) -> tuple[str, str]:
    executable = shutil.which("browser-act")
    if not executable:
        return "", "existing Chrome mode requires browser-act; install with: uv tool install browser-act-cli --python 3.12"
    try:
        result = subprocess.run(
            [executable, "browser", "list"],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return "", f"failed to list browser-act browsers: {exc}"
    if result.returncode != 0:
        return "", _browser_act_error(result)
    pattern = re.compile(rf'^id=(\S+)\s+name=["\']{re.escape(browser_name)}["\']\s+type=chrome-direct\b', re.MULTILINE)
    match = pattern.search(result.stdout)
    if not match:
        return "", f'existing Chrome browser "{browser_name}" was not found or is not chrome-direct'
    return match.group(1), ""


def fetch_with_existing_chrome(url: str, timeout: int, browser_name: str) -> FetchResult:
    browser_id, resolve_error = _resolve_browser_act_id(browser_name, timeout)
    if not browser_id:
        return FetchResult(False, "", url, None, "", resolve_error)

    executable = shutil.which("browser-act") or "browser-act"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    session_name = f"url-md-{digest}-{os.getpid()}"
    opened = False
    try:
        open_result = subprocess.run(
            [executable, "--session", session_name, "browser", "open", browser_id, url],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout + 30,
        )
        if open_result.returncode != 0:
            return FetchResult(False, "", url, None, "", _browser_act_error(open_result))
        opened = True
        subprocess.run(
            [executable, "--session", session_name, "wait", "stable"],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout + 30,
        )
        if detect_page_type(url) == "zhihu":
            selector_result = subprocess.run(
                [
                    executable,
                    "--session",
                    session_name,
                    "wait",
                    "selector",
                    "--selector",
                    ".Post-RichText, .RichContent-inner, .RichText.ztext",
                    "--state",
                    "attached",
                    "--timeout",
                    str(timeout * 1000),
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout + 30,
            )
            if selector_result.returncode != 0:
                return FetchResult(False, "", url, None, "", _browser_act_error(selector_result))
        html_result = subprocess.run(
            [executable, "--session", session_name, "get", "html"],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout + 30,
        )
        if html_result.returncode != 0:
            return FetchResult(False, "", url, None, "", _browser_act_error(html_result))
        return FetchResult(True, html_result.stdout, url, None, "text/html; charset=utf-8")
    except subprocess.TimeoutExpired as exc:
        return FetchResult(False, "", url, None, "", f"browser-act timed out: {exc}")
    finally:
        if opened:
            try:
                close_result = subprocess.run(
                    [executable, "session", "close", session_name],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=30,
                )
                if close_result.returncode != 0:
                    print(f"Warning: failed to close browser-act session: {_browser_act_error(close_result)}", file=sys.stderr)
            except (subprocess.TimeoutExpired, OSError) as exc:
                print(f"Warning: failed to close browser-act session: {exc}", file=sys.stderr)


def prepare_html_for_save(html: str) -> HtmlSavePreparation:
    """Make fetched HTML easier to view from disk without changing page meaning."""
    protocol_count = 0
    lazy_count = 0

    def normalize_protocol_relative(match: re.Match[str]) -> str:
        nonlocal protocol_count
        protocol_count += 1
        return f"{match.group(1)}https://"

    normalized_html = re.sub(
        r'((?:src|href|data-src|content)=["\'])//',
        normalize_protocol_relative,
        html,
        flags=re.IGNORECASE,
    )
    normalized_html = re.sub(
        r'(url\(["\']?)//',
        normalize_protocol_relative,
        normalized_html,
        flags=re.IGNORECASE,
    )

    def attr_value(tag: str, name: str) -> Optional[str]:
        match = re.search(
            rf'\s{name}\s*=\s*(["\'])(.*?)\1',
            tag,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return html_lib.unescape(match.group(2)) if match else None

    def rewrite_img(match: re.Match[str]) -> str:
        nonlocal lazy_count
        tag = match.group(0)
        data_src = attr_value(tag, "data-src")
        if not data_src:
            return tag

        src_match = re.search(
            r'\ssrc\s*=\s*(["\'])(.*?)\1',
            tag,
            flags=re.IGNORECASE | re.DOTALL,
        )
        escaped_data_src = html_lib.escape(data_src, quote=True)
        if src_match:
            if src_match.group(2).strip():
                return tag
            lazy_count += 1
            return tag[: src_match.start(2)] + escaped_data_src + tag[src_match.end(2) :]

        lazy_count += 1
        insert_at = -2 if tag.endswith("/>") else -1
        return tag[:insert_at] + f' src="{escaped_data_src}"' + tag[insert_at:]

    prepared_html = re.sub(
        r"<img\b[^>]*>",
        rewrite_img,
        normalized_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return HtmlSavePreparation(
        html=prepared_html,
        lazy_images_fixed=lazy_count,
        protocol_relative_urls_fixed=protocol_count,
    )


def extract_article_html(page_type: str, html: str) -> ArticleExtraction:
    if page_type == "zhihu":
        for class_name, strategy in (
            ("Post-RichText", "zhihu:post-richtext"),
            ("RichContent-inner", "zhihu:richcontent-inner"),
            ("RichText", "zhihu:richtext"),
            ("ztext", "zhihu:ztext"),
        ):
            extracted = _extract_first_element(
                html,
                lambda tag, expected=class_name: _attr_contains(tag, "class", expected),
            )
            if extracted is not None:
                title = extract_title(html)
                title_html = f"<h1>{html_lib.escape(title)}</h1>\n" if title else ""
                return ArticleExtraction(
                    f"<article>\n{title_html}{extracted}\n</article>",
                    strategy,
                    True,
                    0,
                )
        return ArticleExtraction(html, "zhihu:not_found", False, 0, "zhihu article container not found")

    if page_type == "generic":
        title = extract_title(html)

        def with_title(extracted_html: str) -> str:
            if not title or re.search(r"<h1\b", extracted_html, flags=re.IGNORECASE):
                return extracted_html
            return f"<article>\n<h1>{html_lib.escape(title)}</h1>\n{extracted_html}\n</article>"

        for tag_name in ("article", "main"):
            extracted = _extract_first_element(
                html,
                lambda tag, expected=tag_name: bool(re.match(rf"<{expected}\b", tag, re.IGNORECASE)),
            )
            if extracted is not None:
                return ArticleExtraction(with_title(extracted), f"generic:{tag_name}", True, 0)

        for attr_name, values in (
            ("id", ("article-content", "post-content", "entry-content", "main-content", "content")),
            ("class", ("article-content", "post-content", "entry-content", "main-content")),
        ):
            for value in values:
                extracted = _extract_first_element(
                    html,
                    lambda tag, name=attr_name, expected=value: _attr_contains(tag, name, expected),
                )
                if extracted is not None:
                    return ArticleExtraction(
                        with_title(extracted),
                        f"generic:{attr_name}:{value}",
                        True,
                        0,
                    )
        return ArticleExtraction("", "generic:not_found", False, 0, "semantic article container not found")

    if page_type != "wechat":
        return ArticleExtraction(html, "full_html", False, 0, "unsupported page type")

    extracted = _extract_first_element(
        html,
        lambda tag: _attr_contains(tag, "id", "js_content"),
    )
    strategy = "wechat:js_content"
    if extracted is None:
        extracted = _extract_first_element(
            html,
            lambda tag: _attr_contains(tag, "class", "rich_media_content"),
        )
        strategy = "wechat:rich_media_content"

    if extracted is None:
        return ArticleExtraction(html, "wechat:not_found", False, 0, "wechat article container not found")

    cleaned, removed = _remove_wechat_tail_noise(extracted)
    return ArticleExtraction(cleaned, strategy, True, removed)


def _extract_first_element(html: str, predicate) -> Optional[str]:
    for match in re.finditer(r"<([a-zA-Z][\w:-]*)\b[^>]*>", html):
        tag = match.group(1).lower()
        start_tag = match.group(0)
        if predicate(start_tag):
            return _slice_balanced_element(html, match.start(), match.end(), tag)
    return None


def _slice_balanced_element(html: str, start: int, start_end: int, tag: str) -> str:
    depth = 1
    pattern = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(html, start_end):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[start : match.end()]
        elif not token.rstrip().endswith("/>"):
            depth += 1
    return html[start:]


def _attr_contains(tag: str, attr_name: str, expected: str) -> bool:
    match = re.search(
        rf"\s{re.escape(attr_name)}\s*=\s*([\"'])(.*?)\1",
        tag,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return False
    values = html_lib.unescape(match.group(2)).lower().split()
    return expected.lower() in values


WECHAT_NOISE_ATTR_MARKERS = (
    "qr_code",
    "qrcode",
    "js_pc_qr_code",
    "rich_media_tool",
    "profile_inner",
    "reward_area",
    "mp_profile",
)

WECHAT_TAIL_TEXT_MARKERS = (
    "微信扫一扫",
    "扫码关注",
    "长按识别二维码",
    "分享 收藏 点赞 在看",
)


def _remove_wechat_tail_noise(article_html: str) -> tuple[str, int]:
    cut_positions = []
    attr_pattern = re.compile(
        r"<([a-zA-Z][\w:-]*)\b[^>]*(?:id|class)\s*=\s*([\"'])(.*?)\2[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in attr_pattern.finditer(article_html):
        attr_value = html_lib.unescape(match.group(3)).lower()
        if any(marker in attr_value for marker in WECHAT_NOISE_ATTR_MARKERS):
            cut_positions.append(match.start())

    for marker in WECHAT_TAIL_TEXT_MARKERS:
        index = article_html.find(marker)
        if index >= 0:
            cut_positions.append(_start_of_containing_element(article_html, index))

    if not cut_positions:
        return article_html, 0

    cut_at = min(cut_positions)
    closing = _root_closing_tag(article_html)
    return article_html[:cut_at].rstrip() + ("\n" + closing if closing else ""), 1


def _start_of_containing_element(html: str, index: int) -> int:
    start = html.rfind("<", 0, index)
    end = html.rfind(">", 0, index)
    if start > end:
        return start
    return index


def _root_closing_tag(html: str) -> str:
    match = re.match(r"\s*<([a-zA-Z][\w:-]*)\b", html)
    if not match:
        return ""
    closing = f"</{match.group(1).lower()}>"
    return closing if html.rstrip().lower().endswith(closing) else ""


def _browser_has_zhihu_article(page) -> bool:
    return bool(
        page.locator(".Post-RichText, .RichContent-inner, .RichText.ztext, .ztext").count()
    )


def _wait_for_zhihu_login(context, page, url: str, login_timeout: int) -> bool:
    print(
        "未检测到知乎文章正文。请在打开的 Chrome 窗口中登录知乎；登录完成后脚本会自动重试。",
        file=sys.stderr,
    )
    login_page = context.new_page()
    login_page.goto("https://www.zhihu.com/signin", wait_until="domcontentloaded", timeout=30_000)
    deadline = time.monotonic() + login_timeout
    last_reload = 0.0
    while time.monotonic() < deadline:
        if _browser_has_zhihu_article(page):
            return True
        cookies = context.cookies("https://www.zhihu.com")
        if any(cookie.get("name") == "z_c0" for cookie in cookies):
            now = time.monotonic()
            if now - last_reload >= 3:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                last_reload = now
                if _browser_has_zhihu_article(page):
                    return True
        time.sleep(1)
    return False


def fetch_with_browser(
    url: str,
    timeout: int,
    user_data_dir: Path,
    headed: bool,
    login_timeout: int = DEFAULT_LOGIN_TIMEOUT,
) -> FetchResult:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return FetchResult(
            False,
            "",
            url,
            None,
            "",
            "browser fallback requires playwright and Google Chrome; install with: python3 -m pip install playwright",
        )

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir.expanduser()),
                channel="chrome",
                headless=not headed,
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1365, "height": 900},
            )
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            except PlaywrightTimeoutError:
                pass
            if detect_page_type(page.url) == "zhihu" and not _browser_has_zhihu_article(page):
                if headed and not _wait_for_zhihu_login(context, page, url, login_timeout):
                    context.close()
                    return FetchResult(
                        False,
                        "",
                        url,
                        None,
                        "",
                        f"等待知乎登录或文章正文超时（{login_timeout} 秒）",
                    )
            html = page.content()
            final_url = page.url
            status_code = response.status if response else None
            content_type = ""
            if response:
                content_type = response.headers.get("content-type", "")
            context.close()
            return FetchResult(True, html, final_url, status_code, content_type)
    except PlaywrightError as exc:
        return FetchResult(False, "", url, None, "", f"browser error: {exc}")


def save_result(
    html: str,
    paths: OutputPaths,
    original_url: str,
    final_url: str,
    method: str,
    status_code: Optional[int],
    content_type: str,
    analysis: HtmlAnalysis,
    fallback_used: bool,
    fallback_reason: str,
    error: str,
    degraded: bool = False,
    degraded_reason: str = "",
) -> Dict[str, object]:
    extraction = extract_article_html(analysis.page_type, html)
    prepared = prepare_html_for_save(extraction.html)
    paths.html_path.parent.mkdir(parents=True, exist_ok=True)
    paths.raw_html_path.write_text(html, encoding="utf-8")
    paths.html_path.write_text(prepared.html, encoding="utf-8")

    metadata: Dict[str, object] = {
        "original_url": original_url,
        "final_url": final_url,
        "method": method,
        "status_code": status_code,
        "content_type": content_type,
        "title": analysis.title,
        "page_type": analysis.page_type,
        "is_wechat": analysis.page_type == "wechat",
        "is_zhihu": analysis.page_type == "zhihu",
        "suspicious": analysis.suspicious,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "error": error,
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "html_path": str(paths.html_path),
        "raw_html_path": str(paths.raw_html_path),
        "meta_path": str(paths.meta_path),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "analysis": asdict(analysis),
        "article_extraction": {
            "used": extraction.used,
            "strategy": extraction.strategy,
            "noise_blocks_removed": extraction.noise_blocks_removed,
            "reason": extraction.reason,
        },
        "html_postprocess": {
            "lazy_images_fixed": prepared.lazy_images_fixed,
            "protocol_relative_urls_fixed": prepared.protocol_relative_urls_fixed,
        },
    }
    paths.meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    paths = build_output_paths(args.url, output_dir)
    fallback_used = False
    fallback_reason = ""
    method = "existing-chrome" if args.existing_chrome else ("browser" if args.browser else "http")

    if args.existing_chrome:
        result = fetch_with_existing_chrome(args.url, args.timeout, args.browser_name)
    elif args.browser:
        result = fetch_with_browser(
            args.url, args.timeout, Path(args.user_data_dir), args.headed, args.login_timeout
        )
    else:
        result = fetch_with_http(args.url, args.timeout)

    if result.ok:
        analysis = analyze_html(
            result.final_url,
            result.html,
            result.status_code,
            result.content_type,
        )
    else:
        analysis = HtmlAnalysis(
            page_type=detect_page_type(args.url),
            title="",
            suspicious=True,
            fallback_reason=result.error,
            has_html_shell=False,
            body_length=0,
        )

    should_fallback = (
        not args.browser
        and not args.existing_chrome
        and not args.no_browser_fallback
        and (not result.ok or analysis.suspicious)
    )
    if should_fallback:
        http_result = result
        http_analysis = analysis
        fallback_used = True
        fallback_reason = result.error or analysis.fallback_reason
        browser_result = fetch_with_browser(
            args.url, args.timeout, Path(args.user_data_dir), args.headed, args.login_timeout
        )
        if browser_result.ok:
            result = browser_result
            method = "browser"
            analysis = analyze_html(
                result.final_url,
                result.html,
                result.status_code,
                result.content_type,
            )
        elif _can_use_degraded_result(http_result, http_analysis):
            result = http_result
            analysis = http_analysis
            method = "http"
            degraded_reason = f"{fallback_reason}; browser fallback failed: {browser_result.error}"
            metadata = save_result(
                html=result.html,
                paths=paths,
                original_url=args.url,
                final_url=result.final_url,
                method=method,
                status_code=result.status_code,
                content_type=result.content_type,
                analysis=analysis,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                error=browser_result.error,
                degraded=True,
                degraded_reason=degraded_reason,
            )
            if args.stdout:
                sys.stdout.write(paths.html_path.read_text(encoding="utf-8"))
            else:
                print(f"HTML saved to {metadata['html_path']}")
                print(f"Raw HTML saved to {metadata['raw_html_path']}")
                print(f"Metadata saved to {metadata['meta_path']}")
                print(f"Warning: degraded result: {degraded_reason}", file=sys.stderr)
            return 2
        else:
            result = FetchResult(
                False,
                "",
                browser_result.final_url,
                browser_result.status_code,
                browser_result.content_type,
                f"{fallback_reason}; browser fallback failed: {browser_result.error}",
            )

    if not result.ok:
        paths.meta_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "original_url": args.url,
            "final_url": result.final_url,
            "method": method,
            "status_code": result.status_code,
            "content_type": result.content_type,
            "title": analysis.title,
            "page_type": analysis.page_type,
            "is_wechat": analysis.page_type == "wechat",
            "is_zhihu": analysis.page_type == "zhihu",
            "suspicious": True,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason or analysis.fallback_reason,
            "error": result.error,
            "degraded": False,
            "degraded_reason": "",
            "html_path": "",
            "raw_html_path": "",
            "meta_path": str(paths.meta_path),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "analysis": asdict(analysis),
        }
        paths.meta_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"ERROR: {result.error}", file=sys.stderr)
        print(f"Metadata saved to {paths.meta_path}", file=sys.stderr)
        return 1

    stdout_html = prepare_html_for_save(result.html).html
    metadata = save_result(
        html=result.html,
        paths=paths,
        original_url=args.url,
        final_url=result.final_url,
        method=method,
        status_code=result.status_code,
        content_type=result.content_type,
        analysis=analysis,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        error="",
    )

    if args.stdout:
        sys.stdout.write(stdout_html)
    else:
        print(f"HTML saved to {metadata['html_path']}")
        print(f"Raw HTML saved to {metadata['raw_html_path']}")
        print(f"Metadata saved to {metadata['meta_path']}")
        if analysis.suspicious:
            print(f"Warning: suspicious result: {analysis.fallback_reason}", file=sys.stderr)

    return 0 if not analysis.suspicious else 2


def _can_use_degraded_result(result: FetchResult, analysis: HtmlAnalysis) -> bool:
    if not result.ok or not result.html or not analysis.has_html_shell:
        return False
    if analysis.page_type == "wechat":
        return _has_wechat_article_structure(result.html)
    if analysis.page_type == "zhihu":
        return _has_zhihu_article_structure(result.html)
    return bool(analysis.title and analysis.body_length >= 120)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch a URL's HTML source and save metadata.")
    parser.add_argument("url", help="Target URL to fetch.")
    parser.add_argument("--output-dir", default="output", help="Directory for .html and .json files.")
    parser.add_argument("--browser", action="store_true", help="Force Playwright browser mode.")
    parser.add_argument(
        "--existing-chrome",
        action="store_true",
        help="Use a browser-act chrome-direct browser that inherits the user's existing login state.",
    )
    parser.add_argument(
        "--browser-name",
        default=DEFAULT_EXISTING_CHROME_NAME,
        help="browser-act chrome-direct browser name used by --existing-chrome.",
    )
    parser.add_argument(
        "--no-browser-fallback",
        action="store_true",
        help="Do not start browser mode when HTTP result is suspicious.",
    )
    parser.add_argument("--headed", action="store_true", help="Show browser window in browser mode.")
    parser.add_argument("--timeout", type=int, default=30, help="Request and browser timeout in seconds.")
    parser.add_argument(
        "--user-data-dir",
        default=str(DEFAULT_BROWSER_PROFILE),
        help="Persistent browser profile directory for login state.",
    )
    parser.add_argument(
        "--login-timeout",
        type=int,
        default=DEFAULT_LOGIN_TIMEOUT,
        help="Seconds to wait for interactive login in headed browser mode.",
    )
    parser.add_argument("--stdout", action="store_true", help="Print fetched HTML to stdout as well.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
