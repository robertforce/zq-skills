# 手动配置 PI 使用 Codex 订阅模型

适用于 macOS，使用本目录现成脚本逐步操作，无需 Agent。所有命令在同一个终端窗口分段执行；报错时先处理，不继续后面的步骤。

## 1. 准备软件、账号及兼容版本

```bash
uname -s
node --version
command -v node
npm --version
codex --version
pi --version
```

系统为 Darwin，Node 至少为 22，且满足所装 PI 的要求，优先使用稳定版本。Codex 尚未登录时执行 `codex login`，按提示完成本机 ChatGPT 登录。本方案要求文件形式的 OAuth 凭据；若只保存在钥匙串，先解决文件来源。不要跨电脑复制认证或用 API key 代替订阅登录。

PI 必须支持 openai-codex，并仅依据保存的 expires 判断刷新。首次使用或升级后，先按 [Agent 文档的兼容性检查](AGENT_SETUP.md#1-发现环境确认兼容) 核对实际实现；不确定时可请 Agent 完成代码检查。若新增 JWT exp 或 401 强制刷新，本方案不能直接套用。

正常退出正在使用旧认证的 PI 会话，避免已有刷新继续写回。现有 Harness 账号和任务无需调整。

## 2. 确认目录和旧任务

在终端进入收到的 **pi 部署包目录**，应看到三个 mjs 文件、package.json 和锁文件。可从 Finder 的文件夹服务菜单打开终端。

```bash
SOURCE_DIR="$PWD"
INSTALL_DIR="$HOME/.local/share/pi-codex-sync"
export CODEX_HOME="$HOME/.codex"
export PI_CODING_AGENT_DIR="$HOME/.pi/agent"
test -f "$SOURCE_DIR/sync-codex-auth.mjs" && \
test -f "$CODEX_HOME/auth.json"
```

自定义认证目录请改成实际绝对路径。test 成功无输出，可紧接着执行 `echo $?` 检查，0 为成功。不要 cat 认证文件或把其内容发给他人。

检查已有任务：

```bash
launchctl print gui/$(id -u)/local.codex-pi-sync \
  | grep -E 'path =|program =|runs =|last exit code|run interval'
```

若提示 Could not find service，跳过卸载。若存在，确认属于本方案后执行，避免更新时旧任务仍运行：

```bash
launchctl bootout gui/$(id -u)/local.codex-pi-sync
```

同名文件属于其他用途时先解决冲突，不覆盖。其他卸载错误也先处理。

## 3. 安装独立脚本

```bash
mkdir -p "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR"
cp "$SOURCE_DIR"/*.mjs "$SOURCE_DIR/package.json" "$SOURCE_DIR/package-lock.json" "$INSTALL_DIR/"
npm ci --prefix "$INSTALL_DIR" --ignore-scripts --no-audit --no-fund
node --check "$INSTALL_DIR/sync-codex-auth.mjs"
```

依赖安装成功且语法检查无报错才继续。固定依赖为 proper-lockfile 4.1.2，不修改 PI 安装包。

## 4. 备份并同步一次

```bash
if test -f "$PI_CODING_AGENT_DIR/auth.json"; then
  BACKUP_FILE="$PI_CODING_AGENT_DIR/auth.json.before-codex-sync-$(date +%Y%m%d-%H%M%S)"
  /usr/bin/install -m 600 "$PI_CODING_AGENT_DIR/auth.json" "$BACKUP_FILE"
fi
node "$INSTALL_DIR/sync-codex-auth.mjs"
echo $?
```

退出码应为 0。有变化时显示安全的成功信息，无变化时静默。脚本仅更新 openai-codex 项，保留其他 provider，不改写 Codex 源文件。备份含真实凭据，留在私有认证目录，不放进 Git。

## 5. 设置每 60 秒执行

```bash
node "$INSTALL_DIR/install-launch-agent.mjs"
plutil -lint "$HOME/Library/LaunchAgents/local.codex-pi-sync.plist"
launchctl enable gui/$(id -u)/local.codex-pi-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-pi-sync.plist"
```

plutil 应输出 OK，加载成功通常无输出。生成器自动记录当前 Node 的真实绝对路径和认证目录，无需手写 XML。不使用 sudo，终端可以关闭。

任务加载后立即执行一次，之后在用户登录且系统可运行时每 60 秒触发，休眠期间不保证按分钟执行。

## 6. 检查结果与选择模型

```bash
node "$INSTALL_DIR/verify-sync.mjs"
launchctl print gui/$(id -u)/local.codex-pi-sync \
  | grep -E 'state =|program =|runs =|last exit code|run interval'
tail -n 30 "$HOME/Library/Logs/codex-pi-sync.error.log"
```

六项布尔结果均应为 true，最近退出码为 0，间隔为 60 seconds。短任务的 state = not running 是正常等待。

记录 runs，保持电脑唤醒，约 70 秒后再次检查。runs 应增加，退出码仍为 0，错误日志没有新增错误。只看到任务已加载不算成功。

```bash
pi --list-models openai-codex
pi
```

在 PI 输入 `/model`，选择 openai-codex 下实际列出的模型。可发送“只回复 OK”验证推理，会消耗订阅额度；模型可见不等于请求成功。

固定 expires 为 4102444800000 只避免本地刷新，不延长真实令牌有效期。短同步间隔也不会让 Codex 主动刷新；认证失败时先处理 Codex 登录/刷新，再等待同步。

## 7. 管理任务

手动触发：

```bash
launchctl kickstart gui/$(id -u)/local.codex-pi-sync
```

停止并禁止下次登录启动：

```bash
launchctl bootout gui/$(id -u)/local.codex-pi-sync
launchctl disable gui/$(id -u)/local.codex-pi-sync
```

恢复：

```bash
launchctl enable gui/$(id -u)/local.codex-pi-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-pi-sync.plist"
```

停止同步不会删除已经保存的 PI 认证。

## 8. 故障处理与卸载

| 现象 | 处理 |
| --- | --- |
| 78: EX_CONFIG，旧 Node 不存在 | 按下一段重新生成任务 |
| 找不到 proper-lockfile | 执行 `npm ci --prefix "$INSTALL_DIR" --ignore-scripts` |
| Could not find service | 校验 plist 后按第 5 节加载 |
| service already loaded | 确认任务后先 bootout，再 bootstrap |
| 同步报错 | 检查源登录、JSON、权限及锁，不随意删除活进程锁 |
| 同步成功但请求失败 | 检查 Codex 登录、真实令牌有效性及所选 provider |

Node 升级/移除或安装目录移动后，在同一终端重设正确的 CODEX_HOME、PI_CODING_AGENT_DIR 和 INSTALL_DIR，确认 `node --version`、`command -v node` 指向可用版本。已加载则先 bootout，再按第 5 节重新生成、校验和加载，随后重做周期验证。

彻底卸载时先停止并禁用任务，再只移除本方案的 plist、安装目录和对应日志。若撤销认证，正常退出 PI 后只删除或恢复 openai-codex 项，保留其他 provider 及备份后新增配置，不整份覆盖旧备份。Codex 文件和 Harness 任务保持不变。
