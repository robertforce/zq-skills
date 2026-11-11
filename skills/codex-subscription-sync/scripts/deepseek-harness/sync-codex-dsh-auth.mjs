#!/usr/bin/env node
// 单向同步 Codex access token 到 Harness；不复制 refresh token，不访问网络。
// 用法：node sync-codex-dsh-auth.mjs；可由 launchd 每分钟执行。
// CODEX_HOME、DSH_HOME 可覆盖默认目录，DSH_CREDENTIALS_PATH 可覆盖目标文件。
// 依赖同目录安装的 yaml@2.9.0；仅更新 refs.CODEX_SUBSCRIPTION_ACCESS_TOKEN。

import { createHash, randomUUID } from "node:crypto";
import { chmod, lstat, mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { Document, isMap, parseDocument } from "yaml";

const REF = "CODEX_SUBSCRIPTION_ACCESS_TOKEN";

try {
	await syncCodexAccessToken();
} catch (error) {
	// 解析器的错误可能包含凭据原文；日志只允许安全的错误码。
	const code = typeof error?.code === "string" && /^[A-Z_]+$/.test(error.code) ? ` (${error.code})` : "";
	console.error(`Codex → Harness 认证同步失败${code}；请检查源登录、目标 YAML、权限及文件锁。`);
	process.exitCode = 1;
}

async function syncCodexAccessToken() {
	const source = join(expandPath(process.env.CODEX_HOME || "~/.codex"), "auth.json");
	const target = expandPath(process.env.DSH_CREDENTIALS_PATH || join(process.env.DSH_HOME || "~/.dsh", ".credentials.yaml"));
	const token = await readAccessToken(source);
	await mkdir(dirname(target), { recursive: true, mode: 0o700 });
	await withHarnessLock(target, async () => {
		const targetStat = await lstat(target).catch((error) => {
			if (error.code !== "ENOENT") throw error;
			return undefined;
		});
		// 外部文件边界：禁止覆盖源文件、符号链接及非普通文件。
		const sourceStat = await stat(source);
		if (
			source === target ||
			(targetStat && (!targetStat.isFile() || (targetStat.dev === sourceStat.dev && targetStat.ino === sourceStat.ino)))
		) {
			throw new Error("源目标路径不安全");
		}
		// 获得 App 使用的同一把锁后重新读取，避免覆盖其他进程刚保存的账号。
		const text = targetStat ? await readFile(target, "utf8") : undefined;
		const document = text === undefined ? new Document({ version: 1 }) : parseDocument(text, { uniqueKeys: true });
		if (document.errors.length || !isMap(document.contents)) throw new Error("目标 YAML 无效");
		const data = document.toJS();
		if (data.version !== 1) throw new Error("目标版本不支持");
		for (const section of ["refs", "records"]) {
			if (document.has(section) && !isMap(document.get(section, true))) throw new Error("凭据分节必须为映射");
		}
		for (const [key, value] of Object.entries(data.refs ?? {})) {
			if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) || typeof value !== "string" || !value) {
				throw new Error("目标凭据引用无效");
			}
		}
		if (data.refs?.[REF] === token) {
			await chmod(target, 0o600);
			return;
		}
		document.setIn(["refs", REF], token);
		const temporary = `${target}.${randomUUID()}.tmp`;
		try {
			await writeFile(temporary, document.toString(), { mode: 0o600, flag: "wx" });
			await rename(temporary, target);
		} finally {
			await rm(temporary, { force: true });
		}
	});
}

function expandPath(value) {
	return resolve(value === "~" ? homedir() : value.startsWith("~/") ? join(homedir(), value.slice(2)) : value);
}

async function readAccessToken(source) {
	const data = JSON.parse((await readFile(source, "utf8")).replace(/^\uFEFF/, ""));
	// 外部 Codex 文件边界：只接受订阅登录与 Codex 传输所需的 JWT 账号声明。
	const token = data?.tokens?.access_token;
	if ((data?.auth_mode !== undefined && data.auth_mode !== "chatgpt") || typeof token !== "string" || !token) {
		throw new Error("源文件缺少订阅访问令牌");
	}
	const parts = token.split(".");
	if (parts.length !== 3) throw new Error("访问令牌不是 JWT");
	const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"));
	const account = claims?.["https://api.openai.com/auth"]?.chatgpt_account_id;
	if (typeof account !== "string" || !account || (data.tokens.account_id && data.tokens.account_id !== account)) {
		throw new Error("源文件账号声明不一致");
	}
	return token;
}

// 与 dsh-atomic-write 0.2.2-rc.1 的 wx 文件锁协议兼容；不能用目录锁替代。
async function withHarnessLock(filename, operation) {
	const lock = `${filename}.lock`;
	const deadline = Date.now() + 30_000;
	let waitMs = 20;
	for (;;) {
		try {
			await writeFile(lock, `${process.pid}\n`, { mode: 0o600, flag: "wx" });
			break;
		} catch (error) {
			if (error.code !== "EEXIST") throw error;
			if (await takeOverExitedLock(lock)) continue;
		}
		if (Date.now() >= deadline) throw Object.assign(new Error("等待文件锁超时"), { code: "LOCK_TIMEOUT" });
		await delay(waitMs);
		waitMs = Math.min(waitMs * 2, 200);
	}
	try {
		return await operation();
	} finally {
		await rm(lock, { force: true });
	}
}

async function takeOverExitedLock(lock) {
	const record = await readLockRecord(lock);
	if (record === undefined || !holderExited(record)) return false;
	// 与 App 共用按锁记录哈希命名的接管文件，防止两个接管者删除新持有者的锁。
	const claim = `${lock}.takeover-${createHash("sha256").update(record).digest("hex").slice(0, 16)}`;
	try {
		await writeFile(claim, `${process.pid}\n`, { mode: 0o600, flag: "wx" });
	} catch (error) {
		if (error.code === "EEXIST" || error.code === "EPERM") return false;
		throw error;
	}
	try {
		if ((await readLockRecord(lock)) !== record || !holderExited(record)) return false;
		await rm(lock, { force: true });
		return true;
	} finally {
		await rm(claim, { force: true });
	}
}

async function readLockRecord(lock) {
	try {
		return await readFile(lock, "utf8");
	} catch (error) {
		if (error.code !== "ENOENT") throw error;
		return undefined;
	}
}

function holderExited(record) {
	if (!/^\d+\n$/.test(record)) return false;
	const pid = Number(record.trim());
	if (pid === 0 || pid > 2147483647 || pid === process.pid) return false;
	try {
		process.kill(pid, 0);
		return false;
	} catch (error) {
		return error.code === "ESRCH";
	}
}
