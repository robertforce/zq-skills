---
name: codex-subscription-sync
description: 当用户希望在 macOS 上让 PI 或 DeepSeek Harness 使用本机 Codex 订阅账号模型，或需要检查、修复其认证同步与 launchd 定时任务时使用。支持分别配置或同时配置两个客户端。
---

# Codex 订阅模型接入

复用当前电脑已有的 Codex ChatGPT 文件登录，通过两个独立的本地任务单向同步。Codex 负责刷新令牌，其他账号和未选中的客户端保持原状。

## 选择客户端和操作

从用户请求确定 `PI`、`DeepSeek Harness` 或两者，以及操作是部署、状态检查、修复或卸载。仅在目标不明确且会影响实际写入时询问；“检查状态”只读检查，不重新安装或切换模型。

- **PI：** 阅读 [PI 操作指南](references/pi.md)，使用本 Skill 的 [scripts/pi](scripts/pi) 内置脚本。
- **DeepSeek Harness：** 阅读 [Harness 操作指南](references/deepseek-harness.md)，使用 [scripts/deepseek-harness](scripts/deepseek-harness) 内置脚本。
- **两者：** 分别执行两份指南，分别保存备份并验收。一个失败时报告各自结果，不把部分完成描述为全部成功。

只加载所选客户端的指南。所有相对路径以本 SKILL.md 所在目录为根；将该真实绝对路径设为当前命令环境的 `SKILL_DIR`。即使当前工作目录不同，也从 `"$SKILL_DIR/scripts/<客户端>"` 复制资源。

## 关键约束

| 客户端 | 目标内容 | 刷新处理 |
| --- | --- | --- |
| PI | 仅 auth.json 的 openai-codex 项，含 access/refresh/accountId | 固定本地 expires 为 4102444800000；需确认所有刷新路径仍依赖它 |
| Harness | 仅 refs.CODEX_SUBSCRIPTION_ACCESS_TOKEN | 配置原生 openai-codex 的 apiKeyEnv 引用，显式 key 跳过 OAuth；不复制 refresh 或 expires |

两者文件格式与锁协议不同，保持各自内置脚本。每次首次部署或客户端升级后核对目标版本的实际认证、刷新和锁代码；版本号相同也不能替代核对。不同实现无法确认兼容时停止该分支并说明具体差异。

凭据只在目标电脑本地处理：源 Codex 文件只读；目标仅修改表中指定项，保留其他 provider、refs、records、profile 配置和未选中的任务。首次迁移前正常退出相关客户端，备份保存在私有认证目录，权限 0600。缺少登录时由用户完成本机 codex login；API key 和钥匙串独占存储不直接套用文件方案。

同步脚本不刷新令牌、不调用 OpenAI；60 秒间隔只缩短复制延迟，不保证访问令牌始终有效，也不会让闲置 Codex 主动刷新。用户要求真实推理验证时才执行最小请求，说明订阅额度消耗；模型列表不能证明请求成功。日志只输出安全状态和布尔值，不打印认证原文、账号 ID 或令牌。

## 执行与验收

按所选指南发现当前用户路径和活动 profile，先确认兼容性与现有同名任务，再部署到用户的独立安装目录。更新已有任务时先正常卸载再替换文件，不重复创建调度器。

本 Skill 内置全部运行脚本、package.json 和锁文件。首次用 `npm ci --ignore-scripts` 安装所选客户端依赖；不依赖父仓库或其他 Skill，也不要求原电脑的用户名、Node 路径或源码目录。调度器运行安装目录中的脚本，移动或卸载 Skill 不会立即破坏已部署任务。

只有以下结果全部成立，才报告该客户端部署完成：首次执行退出码 0；至少一次真实定时周期 runs 增加且退出码仍为 0；内置 verify-sync 的全部布尔结果为 true；其他账号和未选中的任务保留。读取 plist 核对 Node 的绝对路径，升级 Node 后按指南重新生成并加载任务，不能只反复 kickstart。

交付时报告所选客户端、兼容版本、真实安装/profile/plist/日志/备份路径、60 秒间隔、首次及周期证据、凭据回读和账号保留结果，以及是否验证在线推理。状态查询、停止、恢复与卸载命令见各自指南的维护部分；卸载仅撤销本方案项，保留之后新增的其他账号。不自动提交代码。
