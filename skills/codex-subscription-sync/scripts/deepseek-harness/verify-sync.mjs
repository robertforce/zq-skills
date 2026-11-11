// 读取任务配置，验证访问令牌、权限与 profile 路由，仅输出布尔结果。
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { parse } from "yaml";

try {
  const plist = join(homedir(), "Library/LaunchAgents/local.codex-dsh-sync.plist");
  const config = JSON.parse(execFileSync("/usr/bin/plutil", ["-convert", "json", "-o", "-", plist], { encoding: "utf8" }));
  const env = config.EnvironmentVariables;
  const source = JSON.parse(readFileSync(join(env.CODEX_HOME, "auth.json"), "utf8").replace(/^\uFEFF/, ""));
  const targetPath = env.DSH_CREDENTIALS_PATH || join(env.DSH_HOME, ".credentials.yaml");
  const target = parse(readFileSync(targetPath, "utf8"));
  const rawPatch = process.env.DSH_PROFILE_PATCH || env.DSH_PROFILE_PATCH || join(env.DSH_HOME, "profiles/desktop/cordis.patch.yml");
  const patchPath = rawPatch.startsWith("~/") ? join(homedir(), rawPatch.slice(2)) : rawPatch;
  const patch = parse(readFileSync(patchPath, "utf8"));
  const checks = {
    credentialVersion: target?.version === 1,
    accessMatches: typeof target?.refs?.CODEX_SUBSCRIPTION_ACCESS_TOKEN === "string" && target.refs.CODEX_SUBSCRIPTION_ACCESS_TOKEN === source.tokens?.access_token,
    routeConfigured: Array.isArray(patch) && patch.some(entry => entry?.id === "llm-pi-ai" && entry.config?.providers?.["openai-codex"]?.apiKeyEnv === "CODEX_SUBSCRIPTION_ACCESS_TOKEN"),
    privatePermissions: (statSync(targetPath).mode & 0o777) === 0o600,
  };
  console.log(JSON.stringify(checks, null, 2));
  if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
} catch {
  console.error("验证失败：检查任务配置、profile 和两端认证文件；未输出凭据。");
  process.exitCode = 1;
}
