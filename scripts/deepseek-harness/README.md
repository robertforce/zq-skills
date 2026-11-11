# Codex 订阅访问令牌同步到 DeepSeek Harness

这是可单独复制到其他 Mac 的部署包。让目标电脑上的 Agent 阅读 [AGENT_SETUP.md](AGENT_SETUP.md) 并执行；无需原电脑的 PI 仓库或 PI 认证文件。

手动操作请阅读 [MANUAL_SETUP.md](MANUAL_SETUP.md)。

## 整体方案

```text
本机 Codex 登录并负责刷新
  ├─ PI 同步任务 → PI 的 openai-codex 认证
  └─ Harness 同步任务 → refs.CODEX_SUBSCRIPTION_ACCESS_TOKEN
                            ↓ 每次新请求解析引用
                      原生 openai-codex 提供方
```

同级 `pi/` 是独立的 PI 部署包。两个任务可以同时运行，都只读 Codex，不相互依赖。

Harness 通过 `@deepseek-ai/dsh-llm-pi-ai` 使用 `@earendil-works/pi-ai`，但有独立的 YAML 凭据存储。路由设置 `apiKeyEnv: CODEX_SUBSCRIPTION_ACCESS_TOKEN` 后，显式访问令牌会优先于 OAuth 记录解析，跳过刷新分支。因此这里只复制 access token，**不复制 refresh token，不设置 expires**。

同步器只修改 `.credentials.yaml` 的指定 refs 项，保留现有账号、其他 refs、records 和注释。它使用与 Harness 兼容的 PID 普通文件锁，锁内重读、同目录原子替换，文件权限 `0600`。不能用 PI 的 proper-lockfile 目录锁替代。

## 文件

| 文件 | 用途 |
| --- | --- |
| `MANUAL_SETUP.md` | 人工逐步操作的命令、成功标准和维护方法 |
| `AGENT_SETUP.md` | 环境发现、源码核对、安装、状态检查及回滚 |
| `sync-codex-dsh-auth.mjs` | 单次同步；不访问网络、不刷新令牌 |
| `configure-route.mjs` | App 正常退出后，备份并合并 profile 路由 |
| `install-launch-agent.mjs` | 用当前 Node、脚本位置及路径环境生成 plist |
| `verify-sync.mjs` | 从任务配置回读路径，只输出布尔结果 |
| `package.json`、`package-lock.json` | 独立固定依赖；`npm ci --ignore-scripts` |
| `LOCAL_DEPLOYMENT.md` | 原电脑的部署状态、验证结果与边界 |

## 版本与限制

已核对的本机构建：Harness `0.2.2-rc.1`、适配器 `0.2.2-rc.1`、pi-ai `1.3.0`。其他电脑即使版本相同，也要核对实际打包代码、活动 profile 和凭据路径。

默认源为 `~/.codex/auth.json`，目标为 `~/.dsh/.credentials.yaml`。支持 `CODEX_HOME`、`DSH_HOME`、`DSH_CREDENTIALS_PATH`。路由工具另支持 `DSH_PROFILE_PATCH`，缺省桌面 profile 为 `~/.dsh/profiles/desktop/cordis.patch.yml`。

`apiKeyEnv` 可解析本地凭据引用；仅 export 终端变量或更新 `.env` 不会持续更新已经启动的桌面 App。`credentials-local` 默认监视文件并重载，新请求才会使用更新后的值。

任务 `local.codex-dsh-sync` 每 60 秒触发。它不会让 Codex 主动刷新，也不会延长真实令牌有效期。真实认证失败时先处理 Codex 登录，不应给 Harness 加入共享 refresh token。

分发整个目录，不附认证、账号 ID、日志、私有备份或 node_modules。模型列表与真实推理分别验收；订阅可用模型取决于账号权限。

## 官方代码依据

- [适配器说明与源码地图](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/README.md)
- [routeAuth 与显式 key 入口](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/src/provider.ts)
- [按请求解析凭据引用](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/src/index.ts)
- [OAuth 记录桥接](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/src/auth.ts)
- [凭据文件格式、监视与优先级](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/credentials/credentials-local/README.md)
- [PID 文件锁与原子替换](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/util/atomic-write/src/index.ts)
