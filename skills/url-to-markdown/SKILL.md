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

基础 HTTP 抓取只使用 Python 标准库。若目标页面需要登录，浏览器兜底需要本机 Google Chrome 和可选的 `playwright` Python 包：

```bash
python3 -m pip install playwright
python3 skills/url-to-markdown/scripts/url_to_markdown.py \
  "https://zhuanlan.zhihu.com/p/ARTICLE_ID" \
  --browser --headed
```

浏览器使用专属资料目录 `~/.url-to-markdown/chrome-profile`。首次运行时在打开的 Chrome 中正常登录；脚本最多等待 5 分钟，检测到文章正文后自动继续。后续普通运行会在公开抓取失败时复用该登录状态进行后台抓取。

如果网站拒绝自动化浏览器登录，可选用 `browser-act` 连接用户已登录的日常 Chrome。该能力必须由用户显式授权，不会自动触发：

```bash
uv tool install browser-act-cli --python 3.12
python3 skills/url-to-markdown/scripts/url_to_markdown.py \
  "https://example.com/private-article" \
  --existing-chrome
```

默认连接名是 `authenticated-chrome`，必须预先配置为 `chrome-direct`；可用 `--browser-name` 修改。连接期间日常 Chrome 会暂时被占用，抓取结束后临时会话自动关闭。

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
- 句子中的行内公式先使用单个 `$` 成对包裹，最外层再使用反引号包裹；独占一行的公式使用 `math` 围栏代码块。
- `zhida.zhihu.com/search` 直达搜索链接只保留链接文字，不保留 Markdown 链接标记和目标地址。
- 末尾包含 `原文链接：<输入 URL>`。

此 skill 不绕过验证码、付费墙或访问控制。验证码和登录操作必须由用户在显示的 Chrome 中自行完成；抓取失败时，报告底层抓取错误并给出恢复命令。
