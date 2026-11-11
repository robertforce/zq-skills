# 手动配置 DeepSeek Harness 使用 Codex 订阅模型

适用于 macOS，使用本目录现成脚本逐步配置，无需 Agent。所有命令在同一个终端窗口分段执行，遇到报错先处理，不继续后面的步骤。

## 1. 准备软件、账号及兼容版本

```bash
uname -s
node --version
command -v node
npm --version
codex --version
```

系统为 Darwin，Node 使用 22 或更高稳定版本。需要已经安装 DeepSeek Harness。Codex 尚未登录时执行 `codex login`，按提示完成本机 ChatGPT 登录。要求文件形式的 OAuth 凭据；钥匙串独占存储先解决文件来源，不跨电脑复制认证，也不用 API key 替代。

已核对构建为 Harness 0.2.2-rc.1、内置 pi-ai 1.3.0。需要原生 openai-codex 路由、显式访问令牌优先解析、凭据自动重载及兼容的 PID 文件锁。首次使用或升级后先按 [Agent 文档的版本检查](AGENT_SETUP.md#1-发现环境与版本) 核对实际代码；不确定时请 Agent 检查。同版本号也不保证构建相同。

本方案只复制 access token，不复制 refresh token 或 expires，刷新由 Codex 负责；原账号与 PI 任务保留。

## 2. 退出 App 并确认路径

从菜单正常退出 Harness，确保没有其他配置写入者。在终端进入收到的 **deepseek-harness 部署包目录**，应看到四个 mjs、package.json 和锁文件。也可从 Finder 文件夹的服务菜单打开终端。

以下是标准桌面路径，自定义 DSH_HOME、凭据文件或其他 profile 时，先改成实际绝对路径：

```bash
SOURCE_DIR="$PWD"
INSTALL_DIR="$HOME/.local/share/codex-dsh-sync"
export CODEX_HOME="$HOME/.codex"
export DSH_HOME="$HOME/.dsh"
export DSH_CREDENTIALS_PATH="$DSH_HOME/.credentials.yaml"
export DSH_PROFILE_PATCH="$DSH_HOME/profiles/desktop/cordis.patch.yml"
test -f "$SOURCE_DIR/sync-codex-dsh-auth.mjs" && \
test -f "$CODEX_HOME/auth.json" && \
test -f "$DSH_PROFILE_PATCH"
```

test 成功无输出，可紧接着执行 `echo $?` 检查，0 为成功。profile 不存在时先确认实际路径及 App 是否完成初次启动，不盲目创建 desktop 目录；Web 模式可能使用 web profile。不要 cat 认证文件或把令牌发给他人。

## 3. 检查旧任务并安装脚本

```bash
launchctl print gui/$(id -u)/local.codex-dsh-sync \
  | grep -E 'path =|program =|runs =|last exit code|run interval'
```

Could not find service 表示未加载，跳过卸载。若存在，确认属于本方案后执行：

```bash
launchctl bootout gui/$(id -u)/local.codex-dsh-sync
```

同名文件属于其他用途时先解决冲突。无需停止 PI 同步任务。然后安装：

```bash
mkdir -p "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR"
cp "$SOURCE_DIR"/*.mjs "$SOURCE_DIR/package.json" "$SOURCE_DIR/package-lock.json" "$INSTALL_DIR/"
npm ci --prefix "$INSTALL_DIR" --ignore-scripts --no-audit --no-fund
node --check "$INSTALL_DIR/sync-codex-dsh-auth.mjs"
```

依赖安装成功且语法检查无报错才继续。yaml 固定为 2.9.0，不修改 App 或 PI 依赖。

## 4. 备份并配置路由

```bash
if test -f "$DSH_CREDENTIALS_PATH"; then
  BACKUP_FILE="$DSH_CREDENTIALS_PATH.before-codex-sync-$(date +%Y%m%d-%H%M%S)"
  /usr/bin/install -m 600 "$DSH_CREDENTIALS_PATH" "$BACKUP_FILE"
fi
node "$INSTALL_DIR/configure-route.mjs"
```

工具会另行备份 profile，并合并指定条目，保留其他 provider 和界面设置。目标条目如下：

```yaml
- id: llm-pi-ai
  config:
    providers:
      openai-codex:
        apiKeyEnv: CODEX_SUBSCRIPTION_ACCESS_TOKEN
```

也可自行用编辑器合并，但不要用这段覆盖整份文件。已有相同 id 时在其 config.providers 中加入路由，不重复建 id；保留其他配置。省略 api 与 baseURL，使用原生 Codex 协议。

工具拒绝无效 YAML、未知标签、重复 id 或已有自定义协议/端点时，先核对原配置，必要时请 Agent 协助保留 `!!js` 等内容后合并，不能清空重试。备份含真实凭据，保留在私有目录，不加入 Git。

## 5. 同步一次并设置定时任务

```bash
node "$INSTALL_DIR/sync-codex-dsh-auth.mjs"
echo $?
```

成功时静默，退出码为 0。脚本只更新 refs.CODEX_SUBSCRIPTION_ACCESS_TOKEN，保留其他 refs、records 和账号，不改写 Codex 源文件。失败时先处理，不加载任务。

保持第 2 节四项路径变量正确：

```bash
node "$INSTALL_DIR/install-launch-agent.mjs"
plutil -lint "$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist"
launchctl enable gui/$(id -u)/local.codex-dsh-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist"
```

plutil 输出 OK，加载成功通常无输出。生成器使用当前 Node 的真实绝对路径，保存脚本目录和路径环境，无需手写 XML。不使用 sudo，终端可以关闭。

加载后立即执行一次，之后在用户登录且系统可运行时每 60 秒触发，休眠期间不保证按分钟执行。

## 6. 检查状态和选择模型

```bash
node "$INSTALL_DIR/verify-sync.mjs"
launchctl print gui/$(id -u)/local.codex-dsh-sync \
  | grep -E 'state =|program =|runs =|last exit code|run interval'
tail -n 30 "$HOME/Library/Logs/codex-dsh-sync.error.log"
```

四项结果均为 true，最近退出码为 0，间隔为 60 seconds。短任务的 state = not running 是正常等待。

记录 runs，保持电脑唤醒，约 70 秒后再次检查，确认 runs 增加、退出码仍为 0，错误日志无新增错误。只看到已加载不算成功。

重新打开 Harness，在模型选择器选择 openai-codex 下实际列出的模型，保留原账号和其他模型；无需再次执行 Harness 的 Codex OAuth 登录。可发“只回复 OK”验证真实推理，会消耗订阅额度；模型可见不等于请求成功。

新模型未出现时，检查活动 profile、插件挂载和加载错误，再正常退出并重开 App。认证失败时先恢复 Codex 登录/刷新，再等待同步；任务不会主动刷新，也不会延长令牌真实有效期。

## 7. 管理任务

手动触发：

```bash
launchctl kickstart gui/$(id -u)/local.codex-dsh-sync
```

停止并禁止下次登录启动：

```bash
launchctl bootout gui/$(id -u)/local.codex-dsh-sync
launchctl disable gui/$(id -u)/local.codex-dsh-sync
```

恢复：

```bash
launchctl enable gui/$(id -u)/local.codex-dsh-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-dsh-sync.plist"
```

停止同步不会清除已经保存的访问令牌。

## 8. 故障处理与卸载

| 现象 | 处理 |
| --- | --- |
| 78: EX_CONFIG，旧 Node 不存在 | 按下一段重新生成任务 |
| 找不到 yaml | 执行 `npm ci --prefix "$INSTALL_DIR" --ignore-scripts` |
| Could not find service | 校验 plist 后按第 5 节加载 |
| 同步失败或锁超时 | 检查源登录、YAML 和权限，不按年龄删除活进程锁 |
| routeConfigured 为 false | 核对实际 profile、路由条目和任务保存的环境 |
| 令牌匹配但请求失败 | 核对 Codex 登录、真实令牌有效性及账号模型权限 |

Node 升级/移除、脚本移动或路径变更后，在同一终端重设第 2 节正确路径，确认当前 node 可用。任务已加载则先 bootout，再按第 5 节重新生成、校验和加载，随后验证一个完整周期。App 或 pi-ai 升级还需重查兼容性。

卸载先停止并禁用任务，再仅删除本方案 plist、安装目录及日志。正常退出 App 后仅撤销指定 refs 引用和路由，保留其他账号及备份后新增配置，不整份旧备份覆盖当前文件，不修改 Codex 源文件或 PI 任务。
