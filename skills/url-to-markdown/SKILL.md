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

默认先用 Python 标准库进行 HTTP 抓取。所有网站遇到请求失败、登录页、验证页或正文缺失时，自动通过 `browser-act` 复用用户已打开、已登录的日常 Chrome；直接进入此回退，不再先启动专属 Playwright 浏览器。用户已授权这一默认行为，后续无需逐次确认。

Chrome 连接需要已安装 `browser-act-cli`，并预先配置名为 `authenticated-chrome` 的 `chrome-direct`；可用 `--browser-name` 指定其他名称。代理首次操作前先加载 browser-act skill 及其使用指南。browser-act 连接不可用时继续检查下述宿主 Chrome 备用路径；两者均不可用才报告底层错误，不另建浏览器身份或保存限制页。

若 browser-act 因调试接口连接失败（例如 `230404`）而无法使用，但当前宿主提供 Chrome 浏览器工具，代理应继续通过该工具复用用户的 Chrome，无需再次确认。优先只读使用已打开的同 URL 标签；否则创建临时标签打开原 URL。读取已渲染的正文 DOM，保留标题、段落、代码和图片 HTML，保存到本地；使用内置 `fetch_html.py` 的 `analyze_html` 和 `save_result` 校验、提取并记录元信息，再用内置 `html_to_markdown.py` 转换，用 `url_to_markdown.py` 的 `finalize_markdown` 补齐目录与原文链接。此分支由代理执行，独立 Python CLI 无法调用宿主工具。若两种 Chrome 连接均不可用，才报告连接错误并停止。

抓取使用临时会话打开目标 URL，保留用户原有标签页；完成或失败后关闭本次临时会话。遇到登录或验证码时提示用户在显示的 Chrome 中处理，最多等待 5 分钟，检测到有效正文后自动继续。`--login-timeout` 可调整等待时间；超时明确报错，不生成限制页 Markdown。

需要跳过 HTTP、直接重试 Chrome 时运行：

```bash
python3 skills/url-to-markdown/scripts/url_to_markdown.py \
  "https://example.com/private-article" \
  --existing-chrome
```

`--no-browser-fallback` 可禁用自动 Chrome 兜底。专属资料目录 `~/.url-to-markdown/chrome-profile` 的 Playwright 模式仅在显式指定 `--browser` 时使用，需要另行安装 `playwright`；`--browser --headed` 可显示其窗口。

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
- 引用正文与 `> ` 位于同一行；多段、换行和嵌套引用保留对应的引用层级。
- 代码块保留原文换行、空行和缩进，识别 `<br>` 和逐行元素表示的换行；源代码只有一行时保持一行。
- 代码围栏根据代码节点、`pre` 或包装节点的明确语言标记填写语言，TypeScript 统一为 `ts`（即以 \`\`\`ts 开始），JavaScript 统一为 `js`；无法确定语言时使用无语言围栏。
- 句子中的行内公式先使用单个 `$` 成对包裹，最外层再使用反引号包裹；独占一行的公式使用 `math` 围栏代码块。
- `zhida.zhihu.com/search` 直达搜索链接只保留链接文字，不保留 Markdown 链接标记和目标地址。
- 末尾包含 `原文链接：<输入 URL>`。

此 skill 不绕过验证码、付费墙或访问控制。验证码和登录操作必须由用户在显示的 Chrome 中自行完成；抓取失败时，报告底层抓取错误并给出恢复命令。
