---
name: url-to-markdown
description: 将 URL、网页或文章链接内容保存为 Markdown 文件。当需要先抓取 URL 为 HTML，再转换为 Markdown，并在文件中添加目录标记和原文链接时使用。
---

# URL 转 Markdown

使用此 skill 将 URL 内容保存为 Markdown 文件。

## 工作流

运行此 skill 目录内置的入口脚本：

```bash
python3 skills/url-to-markdown/scripts/url_to_markdown.py "https://example.com/article"
```

如果用户指定输出目录，使用 `--output-dir` 传入：

```bash
python3 skills/url-to-markdown/scripts/url_to_markdown.py "https://example.com/article" --output-dir ~/documents/markdown
```

默认 Markdown 输出目录是 `~/documents/markdown`。

## 安装可用性规则

安装后必须将此 skill 视为自包含单元。运行时不要调用父项目目录中的脚本。

始终调用 `skills/url-to-markdown/scripts/` 中的内置脚本：

1. `fetch_html.py` 将 URL 保存为 HTML 文件和元信息 JSON。
2. `html_to_markdown.py` 将保存的 HTML 文件转换为 Markdown。
3. `url_to_markdown.py` 串联以上两步并写入最终 Markdown 文件。

如果项目级脚本后续升级，需要先将变更同步到此 skill 的脚本副本中，再重新安装或分发 skill。

## 输出格式

生成的 Markdown 文件必须：

- 使用页面标题作为文件名，并替换不适合文件名的字符。
- 首行包含 `[toc]`。
- 末尾包含 `原文链接：<输入 URL>`。

此 skill 不绕过验证码、登录要求、付费墙或访问控制。抓取失败时，报告底层抓取错误。
