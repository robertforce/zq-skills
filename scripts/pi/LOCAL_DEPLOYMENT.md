# 原电脑部署记录

记录日期：2026-11-11。这是部署经验，其他电脑按 AGENT_SETUP.md 重新发现路径，不照抄本机版本目录。

| 项目 | 本机状态 |
| --- | --- |
| 原运行脚本 | `$HOME/Documents/code/pi/scripts/sync-codex-auth.mjs` |
| 任务 | `local.codex-pi-sync` |
| plist | `$HOME/Library/LaunchAgents/local.codex-pi-sync.plist` |
| 当前 Node | `$HOME/.nvm/versions/node/v26.10.0/bin/node` |
| 源与目标 | `$HOME/.codex/auth.json` → `$HOME/.pi/agent/auth.json` |
| 频率 | 60 秒，RunAtLoad |
| 日志 | `$HOME/Library/Logs/codex-pi-sync.log` 和 `.error.log` |

任务曾因 `$HOME/.nvm/versions/node/v22.17.1/bin/node` 被移除而报 `78: EX_CONFIG`。已备份原 plist，仅将 ProgramArguments 的 Node 路径改为现有 Node 26，重新加载；手动执行、加载首次执行和后续周期执行均成功，退出码为 0，错误日志为空。

回读检查确认 access/refresh 与 Codex 匹配、expires 为 `4102444800000`、权限 0600，其他 provider、原脚本、Codex 源文件及 Harness 任务均未改动。

此目录是可移植分发包的副本。整理它时没有迁移本机任务的运行脚本路径；若以后迁移，先安装本包依赖，再用安装目录下生成器更新原任务并重做验收，不创建第二个同目标任务。

未在本轮验证真实模型推理。原 PI 仓库的 `npm run check` 因缺少 `@biomejs/wasm-nodejs` 未能启动；不将其描述为检查通过。此部署包有自己的 package.json 与锁文件，按 `npm ci --ignore-scripts` 安装即可，不依赖原仓库的完整开发依赖。
