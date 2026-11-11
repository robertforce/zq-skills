# 原电脑部署记录

记录日期：2026-11-11。其他电脑按 AGENT_SETUP.md 重新发现安装和 profile 路径。

| 项目 | 本机状态 |
| --- | --- |
| App | `/Applications/DeepSeek Harness.app`，`0.2.2-rc.1` |
| 内置适配器 / pi-ai | `0.2.2-rc.1` / `1.3.0` |
| 原运行脚本 | `$HOME/Documents/code/pi/scripts/sync-codex-dsh-auth.mjs` |
| 活动 profile patch | `$HOME/.dsh/profiles/desktop/cordis.patch.yml` |
| 凭据文件 | `$HOME/.dsh/.credentials.yaml`，version 1 |
| 任务 | `local.codex-dsh-sync` |
| plist | `$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist` |
| Node | `$HOME/.nvm/versions/node/v26.10.0/bin/node` |
| 日志 | `$HOME/Library/Logs/codex-dsh-sync.log` 和 `.error.log` |
| 频率 | 60 秒，RunAtLoad |

已配置 `openai-codex.apiKeyEnv = CODEX_SUBSCRIPTION_ACCESS_TOKEN`，首次和多次定时执行退出码为 0，错误日志为空。回读确认访问令牌匹配、权限 0600、其他 refs/records 和账号保留，原 profile 的界面配置保留，Codex 源文件未改动。未向 Harness 写入共享 refresh token。

原脚本的 15 项临时测试通过，覆盖其他账号及注释保留、无变化不重写、非法文件拒绝覆盖、源目标隔离、令牌更新、PID 文件锁互斥与死进程锁接管。此目录新增的安装、配置及验证工具另以临时 HOME 验证。

原有 PI 任务仍独立运行，其旧 Node 路径故障随后单独修复。本包整理过程没有改动现有调度器，也没有迁移运行路径；本目录可以作为其他电脑的分发源。

App 界面验证曾中断，未完成在线模型推理；配置和凭据同步成功不能作为订阅服务端权限的证明。本记录不包含账号 ID、令牌、日志或认证备份。
