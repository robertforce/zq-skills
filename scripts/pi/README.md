# Codex 订阅认证同步到 PI

这是可单独复制到其他 Mac 的部署包。让目标电脑上的 Agent 阅读 [AGENT_SETUP.md](AGENT_SETUP.md) 并执行。需要目标电脑已经登录 Codex，且其 PI 版本通过兼容性检查。

手动操作请阅读 [MANUAL_SETUP.md](MANUAL_SETUP.md)。

## 整体方案

```text
本机 Codex 登录、持有原始认证并负责刷新
  ├─ 每 60 秒 → PI auth.json 的 openai-codex 项
  └─ 每 60 秒 → Harness .credentials.yaml 的一个 refs 引用
```

两份同步独立从 Codex 读取，彼此不转发认证；只安装其中一个目录也可运行。Harness 的部署包位于同级 `deepseek-harness/`。

| 客户端 | 同步内容 | 避免客户端刷新的方式 | 写锁 |
| --- | --- | --- | --- |
| PI | access、refresh、accountId、type | 本地 expires 固定为 `4102444800000` | proper-lockfile 目录锁 |
| DeepSeek Harness | 仅 access token | 原生路由的显式 key 覆盖，跳过 OAuth 分支 | Harness 的 PID 文件锁 |

PI 只更新 `openai-codex`，保留其他 provider。固定 expires 是依赖当前实现的技巧，不是延长真实令牌寿命；版本升级后必须重查所有刷新路径。

## 文件

| 文件 | 用途 |
| --- | --- |
| `MANUAL_SETUP.md` | 人工逐步操作的命令、成功标准和维护方法 |
| `AGENT_SETUP.md` | 其他电脑上的自动部署步骤、兼容性门槛及验收 |
| `sync-codex-auth.mjs` | 单次同步；不刷新令牌，不请求网络 |
| `install-launch-agent.mjs` | 使用当前 Node 和本目录生成 plist，不自动加载 |
| `verify-sync.mjs` | 从 plist 读取路径，只输出布尔检查结果 |
| `package.json`、`package-lock.json` | 固定依赖；`npm ci --ignore-scripts` 安装 |
| `LOCAL_DEPLOYMENT.md` | 原电脑已部署状态及 Node 路径故障经验 |

## 使用与限制

先按部署文档安装依赖，再运行 `node sync-codex-auth.mjs`。源目录由 `CODEX_HOME` 指定，目标目录由 `PI_CODING_AGENT_DIR` 指定，缺省为 `~/.codex` 和 `~/.pi/agent`。

`local.codex-pi-sync` 是用户登录会话中的 LaunchAgent，登录且电脑唤醒时每 60 秒运行。短间隔不能保证令牌永不过期，Codex 必须实际完成刷新；失败时恢复 Codex 登录后再同步。

每台电脑使用自己的本机登录。此目录不包含真实 auth.json、令牌、账号 ID、日志、备份或 node_modules。复制整个目录即可分发；无需原 PI 源码仓库。不要将真实认证或私有备份放入这个目录。

模型使用 `openai-codex` provider，模型 ID 以本机实际列表和账号权限为准。出现模型列表不等于推理请求已成功。

## 依据

PI 实现核对入口：`packages/ai/src/auth/resolve.ts`、`packages/ai/src/models.ts`、`packages/ai/src/api/openai-codex-responses.ts`，已安装包则检查其 `dist` 文件。[PI 官方源码](https://github.com/earendil-works/pi/tree/main/packages/ai)、[Apple launchd 使用说明](https://support.apple.com/guide/terminal/apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac)。
