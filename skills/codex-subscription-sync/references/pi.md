# PI 部署与维护

按 SKILL.md 选定本客户端后阅读。先将当前 Skill 的真实绝对路径设为命令环境中的 SKILL_DIR；依赖和脚本均来自本 Skill 内置目录。

## 1. 发现环境，确认兼容

执行 `uname -s`、`command -v node`、`node --version`、`command -v npm`、`command -v pi`、`pi --version`。要求 macOS、Node ≥22、npm、PI。优先使用已安装的受支持稳定版 Node，勿照抄另一台电脑的 nvm 路径。

确认真实的 `CODEX_HOME` 与 `PI_CODING_AGENT_DIR`，缺省分别为 `~/.codex`、`~/.pi/agent`。本文后续命令假定这些变量已解析成当前用户的绝对路径；不同工具调用不一定继承上一次 shell 的 export，应逐次明确传递。

源文件必须是本机订阅 OAuth 登录：`auth_mode` 为 `chatgpt` 或未设置，有非空 `tokens.access_token`、`tokens.refresh_token`，access JWT 的 `payload["https://api.openai.com/auth"].chatgpt_account_id` 非空，若有 `tokens.account_id` 则必须匹配。用程序检查类型与布尔值，不打印原文。缺少登录时由用户完成本机 `codex login`；钥匙串独占存储需先解决文件来源，不能拿 API key 替代。

检查 PI 实际安装实现的全部刷新路径，包括请求前、模型列表及认证失败重试。已核对实现：

- `openai-codex` 认证格式为 `type/access/refresh/expires/accountId`。
- 请求前以 `Date.now() + max(五分钟, 请求最小有效期) >= expires` 判断刷新；模型列表以 `Date.now() >= expires` 判断。
- Codex 传输没有另外按 JWT exp 或 401 强制刷新。
- 凭据写入与 PI 使用相同 proper-lockfile 目录锁；需核对其锁路径和配置。

检查源码 `packages/ai/src/auth/resolve.ts`、`models.ts`、`api/openai-codex-responses.ts`；npm 安装检查实际包的构建文件。若新增绕过 expires 的刷新路径，停止部署并说明差异。固定远期 expires 不能自动适用于新版本。

首次迁移前请用户正常退出正在使用旧认证的 PI 会话，避免已有刷新操作继续写回；不擅自终止进程。

完成条件：路径、文件登录和实际刷新路径均已确认。安装和版本升级按目标电脑既有约定处理。

## 2. 复制整个部署包并安装依赖

定位本 Skill 的内置 PI 包后执行：

```bash
SOURCE_DIR="$SKILL_DIR/scripts/pi"
INSTALL_DIR="$HOME/.local/share/pi-codex-sync"
mkdir -p "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR"
cp "$SOURCE_DIR"/*.mjs "$SOURCE_DIR/package.json" "$SOURCE_DIR/package-lock.json" "$INSTALL_DIR/"
npm ci --prefix "$INSTALL_DIR" --ignore-scripts --no-audit --no-fund
node --check "$INSTALL_DIR/sync-codex-auth.mjs"
```

先检查同名目录及任务；属于本方案则更新同一份，避免两个任务写同一目标。更新已加载任务时先按第 4 节卸载，再复制脚本与安装依赖。属于其他用途则报告名称冲突。依赖固定在包和锁文件中，不修改 PI 安装包或原项目依赖。

完成条件：本目录所有 mjs 和依赖位于同一独立安装目录，语法检查成功。

## 3. 备份与首次同步

为本次 shell 明确设置经过核对的路径，默认示例：

```bash
export CODEX_HOME="$HOME/.codex"
export PI_CODING_AGENT_DIR="$HOME/.pi/agent"
```

若目标 `auth.json` 已存在，在其认证目录内创建一次 `0600` 私有备份：

```bash
if test -f "$PI_CODING_AGENT_DIR/auth.json"; then
  BACKUP_FILE="$PI_CODING_AGENT_DIR/auth.json.before-codex-sync-$(date +%Y%m%d-%H%M%S)"
  /usr/bin/install -m 600 "$PI_CODING_AGENT_DIR/auth.json" "$BACKUP_FILE"
fi
```

记录备份位置，不输出内容；不要把备份放进本部署包或 Git。若任务原已加载，先通过下一节的 print/bootout 流程卸载再更新与首次同步。

```bash
node "$HOME/.local/share/pi-codex-sync/sync-codex-auth.mjs"
```

比较备份与目标：仅 `openai-codex` 项变化，其他 provider 完整保留；Codex 文件未改。无变化时脚本静默，有变化时只输出安全状态。

完成条件：单次退出码为 0，其他账号未变，凭据权限 0600。

## 4. 生成与加载任务

先检查现有任务，print 输出可能含环境值，只向用户报告必要状态：

```bash
launchctl print gui/$(id -u)/local.codex-pi-sync
```

若确为本方案的已加载任务，先执行：

```bash
launchctl bootout gui/$(id -u)/local.codex-pi-sync
```

若不存在则跳过 bootout；其他卸载错误应查原因，不全部静默忽略。使用与首次同步一致的路径变量及已验证 Node：

```bash
node "$HOME/.local/share/pi-codex-sync/install-launch-agent.mjs"
plutil -lint "$HOME/Library/LaunchAgents/local.codex-pi-sync.plist"
launchctl enable gui/$(id -u)/local.codex-pi-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-pi-sync.plist"
```

生成器只生成/更新 plist，已有内容不同则备份；不替你卸载或加载。它记录当前 Node 的真实绝对路径、安装目录及认证环境。首次立即运行，以后每 60 秒触发。使用当前用户 GUI 域，不用 sudo，不创建模型驱动的 Agent 定时聊天。

完成条件：plist 校验 OK，任务加载成功。

## 5. 回读、周期执行与模型验收

```bash
node "$HOME/.local/share/pi-codex-sync/verify-sync.mjs"
launchctl print gui/$(id -u)/local.codex-pi-sync \
  | grep -E 'state =|runs =|last exit code|run interval|program ='
tail -n 30 "$HOME/Library/Logs/codex-pi-sync.error.log"
```

验证器的六个布尔结果必须均为 true。若 Codex 刚刷新，等下一次同步后复查。记录首次 `runs`，电脑保持唤醒，等一个完整周期加调度余量后再次检查，确认 runs 增加且最近退出码仍为 0。Agent 分段等待，及时报告进度。

`state = not running` 对短任务是正常等待；只有“已加载”不算验收成功。任务仅在用户登录、电脑可运行时触发，休眠期间不保证每分钟执行。

核对当前 PI 帮助后，执行 `pi --list-models openai-codex`。用实际列表中的模型，通过 `/model` 或 `pi --provider openai-codex --model <实际ID>` 选择；替换尖括号，不硬编码文档之外的模型。若用户要求端到端验收，发送一条最小请求并说明消耗订阅额度；否则明确未做在线推理验证。

完成条件：首次成功、周期成功、字段匹配、其他账号保留均有证据。

## 6. 状态、停止、恢复、修复与卸载

手动触发：

```bash
launchctl kickstart gui/$(id -u)/local.codex-pi-sync
```

停止及禁止下次登录启动：

```bash
launchctl bootout gui/$(id -u)/local.codex-pi-sync
launchctl disable gui/$(id -u)/local.codex-pi-sync
```

恢复：

```bash
launchctl enable gui/$(id -u)/local.codex-pi-sync
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/local.codex-pi-sync.plist"
```

Node 升级后若旧绝对路径失效，先确认新 Node 可加载 proper-lockfile；用新 Node、正确认证路径重新生成 plist，再 bootout/enable/bootstrap，并重做首次与周期验证。`EX_CONFIG 78` 要先检查 ProgramArguments，不是只反复 kickstart。

其他故障：缺模块则在独立安装目录 `npm ci --ignore-scripts`；终端成功而任务失败则核对绝对路径、环境及明确的 macOS 权限错误；源账号不一致则检查账号切换；同步成功但请求失败则先处理 Codex 登录/刷新与所选 provider。短间隔不会让 Codex 主动刷新。

卸载先停止并禁用任务，再移除本方案的 plist、独立安装目录和日志。恢复 PI 认证时只恢复对应 provider，保留备份后新增的其他 provider；Codex 认证文件始终保留。同步和配置脚本不请求 OpenAI、不主动刷新令牌。

## 交付清单

报告目标版本和兼容性证据、安装/备份/plist/日志路径、任务名与 60 秒间隔、首次及周期退出结果、六项布尔结果、其他账号和 Harness 任务保留情况、模型列表及在线推理是否验证。输出不附令牌、账号 ID 或认证原文。不自动提交代码。

## 官方实现参考

- [PI 模型接入源码](https://github.com/earendil-works/pi/tree/main/packages/ai)
