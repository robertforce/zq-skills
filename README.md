# HTML 抓取工具

抓取指定 URL 的 HTML 源码，并将 HTML 与元信息保存到本地。

## 使用方法

```bash
python3 scripts/fetch_html/fetch_html.py "https://example.com/article"
```

默认会将文件保存到 `output/` 目录：

- `<url_hash>.html`
- `<url_hash>.json`

其中 URL 哈希会基于完整原始 URL 计算，包括 query 参数。

保存 HTML 前，脚本会做轻量后处理，方便本地打开查看：将 `data-src` 等懒加载图片属性补到 `src`，并将 `//res.wx.qq.com/...` 这类协议相对资源地址规范为 `https://...`。

## 浏览器兜底

脚本会先尝试普通 HTTP 请求。如果返回结果疑似受限、正文为空、不是正常文章页，或被平台拦截，可以切换到持久化 Chromium 会话：

```bash
python3 scripts/fetch_html/fetch_html.py --browser --headed "https://www.zhihu.com/..."
```

需要浏览器模式时，先安装依赖：

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

浏览器资料目录默认是 `.browser-profile/`。用户可以先登录一次，后续脚本会复用该登录态。

## 注意事项

- 很多公开微信公众号文章，例如 `mp.weixin.qq.com/s/...`，可以直接通过 HTTP 抓取。
- 脚本不会绕过验证码、付费墙、账号权限或平台访问控制。

# HTML 转 Markdown

将本地 HTML 文件转换为 Markdown：

```bash
python3 scripts/html_to_markdown/html_to_markdown.py path/to/page.html
```

默认输出到同目录的 `path/to/page.md`。可以使用 `-o` 指定输出路径：

```bash
python3 scripts/html_to_markdown/html_to_markdown.py path/to/page.html -o output/page.md
```

当 HTML 中包含相对链接或相对图片地址时，可以使用 `--base-url`：

```bash
python3 scripts/html_to_markdown/html_to_markdown.py page.html --base-url "https://example.com/"
```

# 可安装 Skill 规则

所有 skill 都必须放在项目根目录的 `skills/` 目录下，每个 skill 使用自己的名称作为独立子目录，例如 `skills/url-to-markdown/`。

可安装 skill 必须自包含运行时依赖。skill 安装后只能稳定访问自身目录中的文件，因此 skill 内部调用的脚本必须随 skill 一起放入该 skill 目录，不能依赖项目根目录的 `scripts/`。

如果项目根目录脚本升级，需要同步更新对应 skill 内的脚本副本，再重新安装或分发 skill。`url-to-markdown` 的维护规则是：真正运行以 `skills/url-to-markdown/scripts/` 为准，根目录 `scripts/` 用于项目测试和维护一致性；任何相关行为修改都必须同时更新两份脚本，并运行 `python3 -m unittest discover -s tests` 验证。

## URL 转 Markdown Skill

`skills/url-to-markdown/` 是一个自包含 skill，用于将 URL 内容保存为 Markdown 文件：

```bash
python3 skills/url-to-markdown/scripts/url_to_markdown.py "https://example.com/article"
```

默认输出目录是 `~/documents/markdown`，也可以使用 `--output-dir` 指定目录。生成的 Markdown 文件首行包含 `[toc]`，末尾包含原文链接。

## OpenSpec-Superpowers 衔接 Skill

`skills/openspec-superpowers-bridge/` 用于开始实现 OpenSpec tasks 时衔接 Superpowers 工作流：先读取 OpenSpec 规范和未归档变更文档，再将 design、spec 场景和 tasks 转换为可执行计划、测试用例和规范合规检查步骤。

该 skill 适合在用户说“开始实现”、`apply tasks` 或提到 OpenSpec 变更实现时触发，避免在缺少规范上下文的情况下直接编码。

## 规范合规审查 Skill

`skills/spec-compliance-check/` 用于代码实现完成后、代码审查之前检查实现是否符合 OpenSpec 规范。

该 skill 会要求读取 `openspec/specs/` 主规范、本次 `openspec/changes/` delta 规范、`design.md` 和 `proposal.md`，逐条检查场景覆盖、架构决策和排除范围，防止实现偏离规范。
