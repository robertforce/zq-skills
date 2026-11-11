// 读取已安装任务中的路径，仅输出认证一致性布尔结果。
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

try {
  const plist = join(homedir(), "Library/LaunchAgents/local.codex-pi-sync.plist");
  const config = JSON.parse(execFileSync("/usr/bin/plutil", ["-convert", "json", "-o", "-", plist], { encoding: "utf8" }));
  const sourcePath = join(config.EnvironmentVariables.CODEX_HOME, "auth.json");
  const targetPath = join(config.EnvironmentVariables.PI_CODING_AGENT_DIR, "auth.json");
  const read = (path) => JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
  const source = read(sourcePath);
  const target = read(targetPath)["openai-codex"];
  const payload = JSON.parse(Buffer.from(source.tokens.access_token.split(".")[1], "base64url").toString("utf8"));
  const accountId = source.tokens.account_id || payload["https://api.openai.com/auth"].chatgpt_account_id;
  const checks = {
    oauth: target?.type === "oauth",
    accessMatches: target?.access === source.tokens.access_token,
    refreshMatches: target?.refresh === source.tokens.refresh_token,
    accountMatches: target?.accountId === accountId,
    fixedExpires: target?.expires === 4102444800000,
    privatePermissions: (statSync(targetPath).mode & 0o777) === 0o600,
  };
  console.log(JSON.stringify(checks, null, 2));
  if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
} catch {
  console.error("验证失败：检查任务配置和两端认证文件；未输出任何凭据。");
  process.exitCode = 1;
}
