#!/usr/bin/env node
// 单向同步 Codex OAuth 到 pi；固定本地过期时间，令牌刷新由 Codex 负责。
// 用法：node sync-codex-auth.mjs（单次执行，可由定时任务重复调用）。
// 默认路径：~/.codex/auth.json → ~/.pi/agent/auth.json。
// 可通过 CODEX_HOME 和 PI_CODING_AGENT_DIR 指定源目录和目标目录。
// 依赖同目录安装的 proper-lockfile@4.1.2；不请求网络，不输出令牌。

import { randomUUID } from "node:crypto";
import {
	chmodSync,
	existsSync,
	mkdirSync,
	readFileSync,
	realpathSync,
	renameSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import lockfile from "proper-lockfile";

// 这只是 pi 的本地刷新判断值，不会延长 access token 的真实有效期。
const PI_EXPIRES = 4102444800000;

try {
	await syncCodexAuth();
} catch (error) {
	// JSON 解析错误可能包含原文片段，不能把任意异常消息写入定时任务日志。
	const code = typeof error?.code === "string" && /^[A-Z_]+$/.test(error.code) ? ` (${error.code})` : "";
	console.error(`Codex → pi 认证同步失败${code}；请检查源凭据、目标 JSON、文件权限和文件锁。`);
	process.exitCode = 1;
}

async function syncCodexAuth() {
	const source = join(expandDirectory(process.env.CODEX_HOME || "~/.codex"), "auth.json");
	const target = join(expandDirectory(process.env.PI_CODING_AGENT_DIR || "~/.pi/agent"), "auth.json");
	if (source === target || (existsSync(target) && realpathSync(source) === realpathSync(target))) {
		throw new Error("源和目标不能相同");
	}

	mkdirSync(dirname(target), { recursive: true, mode: 0o700 });
	// 与 pi 使用同一把目录锁；realpath:false 也允许尚未创建的目标文件。
	const release = await lockfile.lock(target, {
		realpath: false,
		stale: 30_000,
		retries: { retries: 20, factor: 1, minTimeout: 250, maxTimeout: 250 },
	});
	try {
		const credential = readCodexCredential(source);
		const data = existsSync(target) ? readJsonObject(target) : {};
		const current = data["openai-codex"];
		if (
			current?.type === credential.type &&
			current.access === credential.access &&
			current.refresh === credential.refresh &&
			current.expires === credential.expires &&
			current.accountId === credential.accountId
		) {
			chmodSync(target, 0o600);
			return;
		}

		data["openai-codex"] = credential;
		const temporary = `${target}.${randomUUID()}.tmp`;
		try {
			writeFileSync(temporary, `${JSON.stringify(data, null, 2)}\n`, { mode: 0o600, flag: "wx" });
			// 在锁内原子替换，避免 pi 读到只写了一半的 JSON。
			renameSync(temporary, target);
		} finally {
			rmSync(temporary, { force: true });
		}
		console.log("已同步 Codex → pi 认证，本地 expires 固定为 2100 年。");
	} finally {
		await release();
	}
}

function expandDirectory(value) {
	return resolve(value === "~" ? homedir() : value.startsWith("~/") ? join(homedir(), value.slice(2)) : value);
}

function readCodexCredential(source) {
	const data = readJsonObject(source);
	const tokens = data.tokens;
	// 边界：外部 Codex 文件必须提供 ChatGPT OAuth 凭据，不能把 API key 当作订阅凭据。
	if (
		(data.auth_mode !== undefined && data.auth_mode !== "chatgpt") ||
		typeof tokens?.access_token !== "string" ||
		!tokens.access_token ||
		typeof tokens.refresh_token !== "string" ||
		!tokens.refresh_token
	) {
		throw new Error("源文件缺少 ChatGPT OAuth 凭据");
	}
	const parts = tokens.access_token.split(".");
	if (parts.length !== 3) throw new Error("access token 不是 JWT");
	const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"));
	const tokenAccountId = payload?.["https://api.openai.com/auth"]?.chatgpt_account_id;
	const accountId = tokens.account_id || tokenAccountId;
	// Codex 请求实现会从 JWT 提取账号；避免保存能通过同步但无法发请求的凭据。
	if (typeof accountId !== "string" || !accountId || accountId !== tokenAccountId) {
		throw new Error("源凭据的账号字段缺失或不一致");
	}
	return { type: "oauth", access: tokens.access_token, refresh: tokens.refresh_token, expires: PI_EXPIRES, accountId };
}

function readJsonObject(path) {
	const data = JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
	// 边界：不能覆盖损坏的认证文件，也不能将数组或标量当作配置对象。
	if (typeof data !== "object" || data === null || Array.isArray(data)) throw new Error("认证文件不是 JSON 对象");
	return data;
}
