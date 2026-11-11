// 正常退出 Harness 后运行；合并指定路由、备份并原子保存 profile patch。
import { randomUUID } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync, chmodSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { isSeq, parseDocument } from "yaml";

const home = process.env.DSH_HOME || join(homedir(), ".dsh");
const raw = process.env.DSH_PROFILE_PATCH || join(home, "profiles/desktop/cordis.patch.yml");
const path = resolve(raw.startsWith("~/") ? join(homedir(), raw.slice(2)) : raw);
const lock = `${path}.lock`;
let locked = false;
let temporary;
try {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  writeFileSync(lock, `${process.pid}\n`, { mode: 0o600, flag: "wx" });
  locked = true;
  const text = existsSync(path) ? readFileSync(path, "utf8") : "[]\n";
  const doc = parseDocument(text);
  if (doc.errors.length || doc.warnings.length || !isSeq(doc.contents)) throw new Error("配置必须是有效 YAML 列表");
  const data = doc.toJS();
  const matches = data.flatMap((entry, index) => entry?.id === "llm-pi-ai" ? [index] : []);
  if (matches.length > 1) throw new Error("插件条目重复");
  const index = matches[0];
  if (index === undefined) {
    doc.add({ id: "llm-pi-ai", config: { providers: { "openai-codex": { apiKeyEnv: "CODEX_SUBSCRIPTION_ACCESS_TOKEN" } } } });
  } else {
    const route = data[index].config?.providers?.["openai-codex"];
    if (route?.api || route?.baseURL) throw new Error("请先核对已有路由的协议与端点");
    doc.setIn([index, "config", "providers", "openai-codex", "apiKeyEnv"], "CODEX_SUBSCRIPTION_ACCESS_TOKEN");
  }
  const next = doc.toString();
  if (text === next) {
    console.log("Codex 路由配置未变。");
  } else {
    if (existsSync(path)) {
      const backup = `${path}.before-codex-sync-${Date.now()}`;
      copyFileSync(path, backup);
      chmodSync(backup, 0o600);
    }
    temporary = `${path}.${randomUUID()}.tmp`;
    writeFileSync(temporary, next, { mode: 0o600, flag: "wx" });
    renameSync(temporary, path);
    console.log("已配置 openai-codex 路由；其他条目和提供方已保留。");
  }
} catch {
  console.error("路由配置失败：检查 App 是否已正常退出、profile 路径、YAML、现有协议和文件锁；未输出配置或凭据。");
  process.exitCode = 1;
} finally {
  if (temporary) rmSync(temporary, { force: true });
  if (locked) rmSync(lock, { force: true });
}
