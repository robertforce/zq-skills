# 项目说明

## 脚本目录规则

- 每个功能脚本都必须放在 `scripts/` 目录下。
- 每个功能都必须在 `scripts/` 下拥有独立子目录。
- 不要将功能脚本直接放在项目根目录。
- 示例：HTML 抓取工具位于 `scripts/fetch_html/fetch_html.py`。

## Skill 内置脚本同步规则

- `skills/url-to-markdown/` 是自包含 skill，实际运行必须使用 `skills/url-to-markdown/scripts/` 内置脚本。
- 根目录 `scripts/` 下的同名脚本用于项目测试、维护和开发对照。
- 修改 `url-to-markdown` 相关脚本时，必须同步修改根目录 `scripts/` 和 `skills/url-to-markdown/scripts/` 两份脚本，避免测试通过但实际 skill 仍运行旧逻辑。
- 同步后应运行 `python3 -m unittest discover -s tests` 验证两份脚本的行为没有分叉。

## Git 提交规则

- git commit 命名必须带有类型前缀，用于表明本次提交的类型。
- 推荐格式：`<type>: <summary>`，例如 `feat: add url-to-markdown skill`、`fix: repair markdown output path`、`docs: update skill rules`。

## HTML 抓取经验

- 保存微信公众号文章 HTML 时，不要假设抓取到的原始源码中的图片资源可以直接显示。
- 微信公众号文章图片经常使用 `data-src` 懒加载，而不是直接使用 `src`；保存 HTML 时，应将非空 `data-src` 补到缺失或为空的 `src` 属性中。
- 保存前应将 `//res.wx.qq.com/...`、`//mmbiz.qpic.cn/...` 这类协议相对资源地址规范为 `https://...`，否则本地 `file://` 打开时可能被错误解析。
- 元信息中应记录 HTML 后处理数量，方便后续检查是否修复了懒加载图片和协议相对 URL。
