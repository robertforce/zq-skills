// 使用当前 Node 与本目录脚本生成用户级 LaunchAgent；不加载或执行任务。
import { copyFileSync, existsSync, mkdirSync, readFileSync, realpathSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const label = "local.codex-dsh-sync";
const scriptName = "sync-codex-dsh-auth.mjs";
const logName = "codex-dsh-sync";
const expand = value => resolve(value === "~" ? homedir() : value.startsWith("~/") ? join(homedir(), value.slice(2)) : value);
const xml = value => value.replace(/[<>&"']/g, char => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" })[char]);

try {
  if (process.platform !== "darwin") throw new Error("仅支持 macOS");
  const installDir = dirname(fileURLToPath(import.meta.url));
  const script = join(installDir, scriptName);
  const node = realpathSync(process.execPath);
  if (!existsSync(script)) throw new Error("同步脚本缺失");
  const env = {
    CODEX_HOME: expand(process.env.CODEX_HOME || "~/.codex"),
    DSH_HOME: expand(process.env.DSH_HOME || "~/.dsh"),
    DSH_CREDENTIALS_PATH: expand(process.env.DSH_CREDENTIALS_PATH || join(process.env.DSH_HOME || "~/.dsh", ".credentials.yaml")),
    DSH_PROFILE_PATCH: expand(process.env.DSH_PROFILE_PATCH || join(process.env.DSH_HOME || "~/.dsh", "profiles/desktop/cordis.patch.yml")),
  };
  const agents = join(homedir(), "Library/LaunchAgents");
  const logs = join(homedir(), "Library/Logs");
  mkdirSync(agents, { recursive: true });
  mkdirSync(logs, { recursive: true });
  const path = join(agents, `${label}.plist`);
  const text = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>${xml(label)}</string>
<key>ProgramArguments</key><array><string>${xml(node)}</string><string>${xml(script)}</string></array>
<key>WorkingDirectory</key><string>${xml(installDir)}</string>
<key>EnvironmentVariables</key><dict>${Object.entries(env).map(([key, value]) => `<key>${xml(key)}</key><string>${xml(value)}</string>`).join("")}</dict>
<key>RunAtLoad</key><true/><key>StartInterval</key><integer>60</integer>
<key>StandardOutPath</key><string>${xml(join(logs, `${logName}.log`))}</string>
<key>StandardErrorPath</key><string>${xml(join(logs, `${logName}.error.log`))}</string>
</dict></plist>
`;
  if (existsSync(path)) {
    if (readFileSync(path, "utf8") === text) {
      console.log(`任务配置未变：${path}`);
      process.exit(0);
    }
    copyFileSync(path, `${path}.before-update-${Date.now()}`);
  }
  const temporary = `${path}.${process.pid}.tmp`;
  try {
    writeFileSync(temporary, text, { mode: 0o644, flag: "wx" });
    renameSync(temporary, path);
  } finally {
    rmSync(temporary, { force: true });
  }
  for (const suffix of [".log", ".error.log"]) {
    writeFileSync(join(logs, `${logName}${suffix}`), "", { mode: 0o600, flag: "a" });
  }
  console.log(`已生成：${path}；请校验并通过 launchctl 加载。`);
} catch {
  console.error("任务配置生成失败；请检查系统、脚本路径及写入权限。未输出凭据。");
  process.exitCode = 1;
}
