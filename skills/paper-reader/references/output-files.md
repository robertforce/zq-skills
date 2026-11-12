# 输出文件契约

除非用户指定其他位置，为每篇论文创建独立目录。原文、译稿和目标文档必须同时保留：

```text
papers/<paper-slug>/
├── manifest.md
├── source/
│   ├── paper.pdf
│   ├── assets/
│   └── supplement/
├── translation/
│   ├── paper.zh-CN.md
│   └── supplement.zh-CN.md
├── reading-record.md
└── article/
    ├── draft.md       # in_review 时存在
    ├── article.md     # approved 后替代 draft.md
    ├── review.md
    └── assets/
```

`draft.md` 与 `article.md` 是同一目标文档在不同生命周期的文件名，不同时保留：审核中使用 `draft.md`，人工批准后重命名为 `article.md`。

使用规范化、稳定且不含个人或内部信息的 `paper-slug`。重跑任务时更新同一论文目录，不创建重复稿件。已有同版本文件时先验证再复用；不要静默覆盖人工修改的译稿或文章。

## manifest.md

至少记录：

- 论文标题、作者、稳定 ID 和版本。
- 原始来源 URL、最终下载 URL 和下载时间。
- `source/paper.pdf` 的 SHA-256 和页数。
- 下载状态：`downloaded` 或 `download_failed`。
- 翻译状态：`translation_complete` 或 `translation_incomplete`。
- 精读状态：`evidence_verified`、`assets_incomplete` 或 `verification_failed`。
- 目标文档状态：`not_started`、`in_review`、`approved` 或 `rejected`。
- 知乎发布状态：`not_prepared`、`publication_pending_human` 或 `published_manually`。
- 人工发布后记录规范知乎 URL、记录来源和 UTC 时间。

只有下载、翻译和精读依次成功，目标文档状态才能进入 `in_review`。只有用户明确确认人工审核通过，状态才能进入 `approved`。

知乎发布状态与目标文档状态分开记录。`approved` 不代表已发布；只有人工实际发布且取得规范公开链接后，才能使用 `published_manually`。不得把 `/write`、`/edit` 或预览页写为公开文章 URL。

## source/

- `paper.pdf` 保存获取到的原始论文，不做改写或压缩。
- `assets/` 保存从原论文提取的图片和复杂表格，文件名稳定并记录原图号和页码。
- `supplement/` 保存补充材料、附录文件或论文源码；没有时可以为空。

## translation/paper.zh-CN.md

完整译稿 frontmatter 至少记录：

```yaml
paper_title: <论文标题>
paper_version: <版本>
source_file: ../source/paper.pdf
translation_status: translation_complete | translation_incomplete
```

正文保持原论文章节和段落顺序，公式与编号不变，并引用 `../source/assets/` 中的本地图片。`translation_status` 只有通过完整性检查后才能设为 `translation_complete`。

## reading-record.md

```md
---
title: <论文标题>
version: <版本>
source_file: ./source/paper.pdf
translation_file: ./translation/paper.zh-CN.md
status: evidence_verified | assets_incomplete | verification_failed
---

# 阅读记录

## 问题与已有方法不足

## 关键贡献

## 实验与收益归因

## 图片与表格资产

| Asset | 来源 | 状态 | 支持结论 | 本地文件 |
| --- | --- | --- | --- | --- |

## 工程判断

## 局限与未回答问题

## 证据索引

| ID | 类型 | 结论 | 原文位置 |
| --- | --- | --- | --- |
```

只有关键证据和资产全部核实时，状态才能是 `evidence_verified`。证据索引必须指向原始论文，不能只指向译稿。

## article/draft.md 与 article/article.md

`in_review` 阶段将目标文档保存为 `article/draft.md`；`approved` 阶段完成审核脚手架清理后，将其重命名为 `article/article.md`，并确认旧的 `draft.md` 不再存在。

目标草稿 frontmatter 至少记录：

```yaml
paper_title: <论文标题>
paper_version: <版本>
source_file: ../source/paper.pdf
translation_file: ../translation/paper.zh-CN.md
review_status: in_review | approved
```

正文结构按论文内容调整，不使用固定章节填充。每个关键数字和判断应能回溯到阅读记录中的证据 ID。图片使用 `./assets/` 相对路径，并在正文中提供来源图号和页码；入选图片从 `source/assets/` 复制而来。

标题优先直接写明研究对象和文章范围，不用“做对了什么”“真正值得看什么”等评价式或设问式包装制造悬念。

默认将文章划分为两个叙事区域：

- 论文主体区：介绍问题、方法、实验、结果和作者经验，不穿插第一人称评价或展开式证据批评。
- 末尾判断区：使用独立章节集中承载 Agent 的取舍、证据边界、工程条件和复现建议。章节名按论文内容确定，不强制使用固定标题。

只有为防止事实误读所需的简短限定可以保留在论文主体区。反模板和判断位置要求见 [evidence-and-writing.md](evidence-and-writing.md)。

自动流程不得将 `review_status` 写为 `approved` 或 `published`。用户明确确认人工审核通过后，允许将 `review_status` 更新为 `approved`；`published` 仍需人工实际发布并提供发布结果。

### 人工批准后的草稿清理

将状态更新为 `approved` 时，同步清理目标文档中只服务于审核流程的内容：

- 删除“待人工审核草稿”等状态提示。
- 删除“审核用证据定位”等内部章节。
- 删除正文中的内部证据 ID 标记，但保留论文链接、Figure/Table 编号、页码和正常来源说明。
- 保留正文中的证据局限与个人判断；它们属于文章内容，不是审核脚手架。

清理完成后将 `article/draft.md` 重命名为 `article/article.md`，在 manifest 中记录最终路径，并更新 `article/review.md` 的文件引用。不得同时保留两个副本，避免后续修改落到错误文件。

证据索引、未核实问题和审核过程继续保存在 `reading-record.md` 与 `article/review.md`，不得因清理公开稿而删除。

## article/review.md

审稿报告包含：

- 建议：`send_to_human`、`revise` 或 `reject`。
- 原始论文、完整译稿和目标文档是否都存在。
- 七项质量评分及理由。
- 阻塞问题。
- 未核实结论清单。
- 图片和表格完整性检查。
- 论文主体区与末尾判断区的叙事边界检查。
- 标题是否准确交代研究对象和内容范围，是否使用泛化评价或悬念包装。
- 对立式模板、固定引导语和编辑腔检查。
- 套话、夸张和虚构经历检查。
- 可执行的修改建议。
- `human_review_required: true`。

人工审核完成后追加 `human_review_status: approved`、非个人化的审核来源（例如 `user_confirmation`）和 UTC 时间。保留自动建议及评分，形成完整审计记录。

自动审稿通过只表示可以送交人工。只有用户明确确认人工审核通过，才记录 `approved`；批准不表示已经发布，也不授权自动发布。

人工发布后追加 `publication_status: published_manually`、`publication_url`、`publication_record_source` 和 `publication_recorded_at_utc`。这些字段同时写入 `manifest.md`，两处必须一致。

若标题使用泛化评价或悬念包装、个人判断散落在论文主体区、同一对立式模板出现两次及以上，或出现可直接删除的编辑腔，审稿建议必须为 `revise`。
