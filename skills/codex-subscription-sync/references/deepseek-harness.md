# DeepSeek Harness 部署与维护

按 SKILL.md 选定本客户端后阅读。先将当前 Skill 的真实绝对路径设为命令环境中的 SKILL_DIR；依赖和脚本均来自本 Skill 内置目录。

## 1. 发现环境与版本

检查 `uname -s`、`node --version`、`command -v node`、`command -v npm`。要求 macOS 和 Node ≥22；优先已安装稳定版。通过 App 的 `Contents/Info.plist` 确认版本，检查实际打包适配器及 pi-ai 精确版本。

已核对的实现是 Harness `0.2.2-rc.1`、pi-ai `1.3.0`。目标电脑必须再确认：

1. 已挂载 `credentials-local` 和 `llm-pi-ai`，插件 id 是 `llm-pi-ai`，内置 `openai-codex` provider 与模型目录存在。
2. `routeAuth()` 为 OAuth-only 目录路由补充显式 key 入口；请求 `apiKey` 优先于 OAuth 记录，跳过刷新分支。检查打包 pi-ai 的 `auth/resolve.js` 及 Codex 传输，不能存在另外无条件刷新路径。
3. `apiKeyEnv` 按请求解析 credentials 引用；`credentials-local` 的 watch 已启用，能自动重载目标文件。
4. 目标版本的 `.lock` 是 `wx` 排他创建的 PID 普通文件，与本同步脚本协议一致。

源码入口：适配器的 provider.ts、index.ts、auth.ts，凭据存储及 atomic-write 实现；链接见本指南末尾。App 的 asar 可只读提取至临时目录检查；不更改签名包。未知新版或锁协议不同则停止，不能仅凭同版本号跳过核对。

确认本机 Codex 文件登录具有 `tokens.access_token`，JWT 包含账号声明，`auth_mode` 为 chatgpt 或缺省，account_id 若有必须匹配。缺少登录由用户完成 `codex login`；钥匙串独占存储先解决文件来源。只输出字段存在性或布尔值。

完成条件：实际实现符合以上四项，源是本机订阅登录。

## 2. 确认活动 profile 和路径

确定真实 `CODEX_HOME`、`DSH_HOME`、`credentials-local.path` 及 App 使用的 profile。默认示例：

```bash
export CODEX_HOME="$HOME/.codex"
export DSH_HOME="$HOME/.dsh"
export DSH_CREDENTIALS_PATH="$DSH_HOME/.credentials.yaml"
export DSH_PROFILE_PATCH="$DSH_HOME/profiles/desktop/cordis.patch.yml"
```

**发现实际值后再使用默认示例**，Web profile 可能为 web，自定义路径以实际配置为准。所有变量使用当前电脑的绝对路径。不同 shell 调用要再次明确传递相同变量。

正常退出 Harness 后再编辑 profile，确保没有其他配置写入者；不擅自终止用户进程。先检查同名任务与安装目录，更新同一任务，避免重复调度器。

## 3. 复制部署包并安装依赖

定位本 Skill 的内置 Harness 包后执行：

```bash
SOURCE_DIR="$SKILL_DIR/scripts/deepseek-harness"
INSTALL_DIR="$HOME/.local/share/codex-dsh-sync"
mkdir -p "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR"
cp "$SOURCE_DIR"/*.mjs "$SOURCE_DIR/package.json" "$SOURCE_DIR/package-lock.json" "$INSTALL_DIR/"
npm ci --prefix "$INSTALL_DIR" --ignore-scripts --no-audit --no-fund
node --check "$INSTALL_DIR/sync-codex-dsh-auth.mjs"
```

更新已加载任务时先按第 5 节卸载，再复制脚本与安装依赖。依赖固定为本目录锁文件中的 yaml；不修改 App 或 PI 依赖。

完成条件：mjs 与其 node_modules 同在独立安装目录，语法检查成功。

## 4. 合并路由和首次同步

若现有任务已加载，先按第 5 节卸载。目标 `.credentials.yaml` 已存在时，在同一私有目录创建一次权限 0600 的备份：

```bash
if test -f "$DSH_CREDENTIALS_PATH"; then
  BACKUP_FILE="$DSH_CREDENTIALS_PATH.before-codex-sync-$(date +%Y%m%d-%H%M%S)"
  /usr/bin/install -m 600 "$DSH_CREDENTIALS_PATH" "$BACKUP_FILE"
fi
```

备份含真实凭据，不能放入部署包或 Git。用程序保存其他 refs/records 的比较快照，不打印内容。

在 Harness 正常退出、路径变量仍正确的环境执行：

```bash
node "$HOME/.local/share/codex-dsh-sync/configure-route.mjs"
node "$HOME/.local/share/codex-dsh-sync/sync-codex-dsh-auth.mjs"
```

路由工具备份 profile 后合并以下条目，不清空已有 YAML：

```yaml
- id: llm-pi-ai
  config:
    providers:
      openai-codex:
        apiKeyEnv: CODEX_SUBSCRIPTION_ACCESS_TOKEN
```

基础组合已经挂载插件，这里只覆盖配置。已有相同 id 时只修改指定路由的 apiKeyEnv，保留其他条目及提供方。工具拒绝无效 YAML、未识别标签、重复 id 或已有自定义协议/端点；出现此类情况先核对真实配置，保留 `!!js` 等内容，不要重建整份文件。

保留 Codex 原生目录协议，省略 api 与 baseURL；不要改成普通 OpenAI provider。同步器只更新 `refs.CODEX_SUBSCRIPTION_ACCESS_TOKEN`，不创建 grant，不复制 refresh、id token 或 expires。版本不为 1、无效 YAML 或不支持的 refs/records 结构会失败，不能覆盖。

完成条件：源未改，目标仅指定引用改变，其他 refs/records/账号完整保留，权限 0600，路由差异只涉及目标项。

## 5. 生成与加载 LaunchAgent

检查是否已加载：

```bash
launchctl print gui/$(id -u)/local.codex-dsh-sync
```

确认存在且属于本方案才执行：

```bash
launchctl bootout gui/$(id -u)/local.codex-dsh-sync
```

不存在就跳过卸载，其他错误查明原因。使用第 2 节的真实绝对路径变量：

```bash
node "$HOME/.local/share/codex-dsh-sync/install-launch-agent.mjs"
plutil -lint "$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist"
launchctl enable gui/$(id -u)/local.codex-dsh-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist"
```

生成器记录当前 Node 的真实绝对路径、脚本位置和四项环境变量；只生成 plist，不加载。已有内容不同则备份。RunAtLoad 立即触发一次，之后每 60 秒触发。不要修改、卸载 PI 的任务，也不用 sudo 或创建 Agent 定时聊天。

完成条件：plist 校验 OK，任务加载成功。

## 6. 验证与选择模型

```bash
node "$HOME/.local/share/codex-dsh-sync/verify-sync.mjs"
launchctl print gui/$(id -u)/local.codex-dsh-sync \
  | grep -E 'state =|runs =|last exit code|run interval|program ='
tail -n 30 "$HOME/Library/Logs/codex-dsh-sync.error.log"
```

四项布尔结果全部为 true，首次退出码为 0。记录 runs，电脑保持唤醒，等一个完整周期加余量后复查 runs 增加、退出码仍为 0，日志无新增错误。短任务的 `not running` 是正常等待；仅看到已加载不算成功。Agent 分段等待并报告进度。

重新打开 Harness，在模型选择器中确认 `openai-codex` 及实际模型；保留原默认模型，让用户选择要用的模型。凭据 watch 只保证重载后的新请求使用新值，不改写已经在途的请求。若新增路由未出现，核对实际 profile、插件挂载、加载错误及 App 是否重启。

模型可见和推理成功分别验收。用户要求端到端测试时，用实际列表里的模型发一条最小请求，说明会消耗订阅额度；未测试就明确报告。不要硬编码另一台电脑的模型名，也不能把可见列表当作账号权限证明。

完成条件：首次、周期执行与字段匹配均有证据，其他账号和 PI 任务保留。

## 7. 日常管理与故障处理

```bash
# 手动触发
launchctl kickstart gui/$(id -u)/local.codex-dsh-sync
# 停止并禁止下次登录启动
launchctl bootout gui/$(id -u)/local.codex-dsh-sync
launchctl disable gui/$(id -u)/local.codex-dsh-sync
# 恢复
launchctl enable gui/$(id -u)/local.codex-dsh-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist"
```

| 故障 | 处理 |
| --- | --- |
| 任务退出 78、旧 Node 路径不存在 | 使用现有稳定 Node 和正确路径重新生成 plist，再卸载/加载并验证周期 |
| 找不到 yaml | 在独立安装目录执行 `npm ci --ignore-scripts` |
| 同步报错 | 检查源登录、YAML 版本、权限、PID 文件锁；不按文件年龄删除活进程锁 |
| App 用到旧值 | 检查真实 credentials 路径及 watch、任务环境、profile 和引用拼写 |
| 同步成功但请求认证失败 | 先恢复 Codex 登录/刷新，等同步后再试；不要让 Harness 刷新共享 refresh token |
| Node、App、pi-ai 升级 | 重新核对代码兼容性；Node 路径改变后重新生成并加载任务 |

定时任务仅在用户登录、系统可运行时触发；60 秒间隔不保证令牌始终有效，也不会触发 Codex 刷新。同步和配置脚本不请求 OpenAI。

卸载时先停止和禁用任务，删除本方案 plist、独立安装目录和日志；在保留后续其他修改的前提下，仅撤销指定 refs 引用和路由。不要整份旧备份覆盖现有账号，不改 Codex 文件或 PI 任务。

## 交付清单

报告 App/适配器/pi-ai 版本及代码核对结论、真实 profile、安装/plist/日志/备份路径、任务名与 60 秒间隔、四项检查、首次与周期证据、其他账号和 PI 任务保留情况，以及模型列表和在线推理的验证边界。不输出令牌、账号 ID 或认证原文，不自动提交代码。

## 官方实现参考

- [模型适配器与源码地图](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/README.md)
- [凭据文件、热重载和解析优先级](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/credentials/credentials-local/README.md)
- [PID 文件锁](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/util/atomic-write/src/index.ts)
