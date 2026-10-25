// W1/W2 — 世界管理的前端数据层(HTTP 契约:routes/worlds.py)。
//
// 一个世界 = 一个库文件 + 一个租户。本模块只放类型、与后端同一规则的名称校验、
// 字节格式化、REST 客户端和错误码 → 中文提示;页面(/worlds)只读这里。
//
// 路径段一律 encodeURIComponent:世界名受 WORLD_NAME_RE 约束本不含特殊字符,
// 但快照 id 等路径段不受此约束,统一编码比逐个判断更不易漏。

import { api, ApiError } from './api';

export type WorldRow = {
	name: string;
	label: string;
	tenant: string;
	created_at: string;
	active: boolean;
	db_bytes: number;
	live_bytes: number;
	statements: number;
	engrams: number;
	snapshots: number;
	snapshot_bytes: number;
};

export type SnapshotRow = {
	id: string;
	kind: 'auto' | 'manual';
	reason: string;
	note: string;
	created_at: string;
	world_time: string;
	size_bytes: number;
};

export type WorldsData = {
	active: string;
	default: string;
	snapshot_retention: number;
	worlds: WorldRow[];
};

/** 与后端 is_valid_world_name 同一规则:小写字母/数字开头,其后可含下划线与连字符,最长 32。 */
export const WORLD_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,31}$/;

export function isValidWorldName(name: string): boolean {
	return WORLD_NAME_RE.test(name);
}

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

/** 1024 进制;B 不带小数,其余保留一位(0→"0 B",1536→"1.5 KB",57 MiB→"57.0 MB")。 */
export function formatBytes(n: number): string {
	if (!Number.isFinite(n) || n <= 0) return '0 B';
	let v = n;
	let i = 0;
	while (v >= 1024 && i < UNITS.length - 1) {
		v /= 1024;
		i++;
	}
	return i === 0 ? `${Math.round(v)} B` : `${v.toFixed(1)} ${UNITS[i]}`;
}

const base = (name: string) => `/api/worlds/${encodeURIComponent(name)}`;

export const worldsApi = {
	list: () => api.get<WorldsData>('/api/worlds'),
	create: (name: string, label?: string) => api.post<WorldRow>('/api/worlds', { name, label }),
	// 切换要等摄入线程停稳 + 重开库,放宽到 60s(后端 ingest_busy 的等待上限是 5s,余量给开库)。
	activate: (name: string) =>
		api.post<{ active: string }>(`${base(name)}/activate`, {}, { timeoutMs: 60_000 }),
	remove: (name: string, confirm: string) =>
		api.del<{ deleted: string }>(`${base(name)}?confirm=${encodeURIComponent(confirm)}`),
	snapshots: (name: string) => api.get<{ snapshots: SnapshotRow[] }>(`${base(name)}/snapshots`),
	// 快照要整库拷贝,大库下远超默认 15s。
	snapshot: (name: string, note?: string) =>
		api.post<SnapshotRow>(`${base(name)}/snapshots`, { note }, { timeoutMs: 120_000 }),
	removeSnapshot: (name: string, id: string) =>
		api.del<{ deleted: string }>(`${base(name)}/snapshots/${encodeURIComponent(id)}`)
};

const ERROR_MESSAGES: Record<string, string> = {
	invalid_world_name: '世界名只能用小写字母、数字、下划线和连字符，最长 32 个字符',
	world_exists: '同名世界已存在',
	world_not_found: '世界不存在',
	world_protected: '默认世界和当前活动世界不能删除',
	confirm_mismatch: '输入的名称与世界名不一致',
	ingest_busy: '摄入任务正在进行，暂时不能切换，请稍后再试',
	world_open_failed: '新世界打不开，已留在原世界',
	snapshot_unsupported_backend: '当前向量后端（zvec）不支持快照',
	insufficient_disk: '磁盘空间不足，快照需要至少 3 倍于数据量的可用空间',
	snapshot_not_found: '快照不存在'
};

/**
 * 后端错误码 → 中文提示(toast 用);未知码兜底为「操作失败：<detail>」。
 * 用 Object.hasOwn 而非 `ERROR_MESSAGES[detail] ?? …`:detail 来自响应体,
 * 'constructor' / 'toString' / '__proto__' 会命中原型链上继承来的函数或对象,
 * `??` 不会回退,函数就被当作提示返回了。
 */
export function worldErrorMessage(detail: string): string {
	return Object.hasOwn(ERROR_MESSAGES, detail)
		? ERROR_MESSAGES[detail]
		: `操作失败：${detail}`;
}

/**
 * 从错误里取出后端 detail。ApiError.message 形如 "<status> <detail>"(见 api.ts),
 * 取第一个空格之后的部分;非 ApiError 原样转字符串。
 * 超时/网络错误的 ApiError.message 没有「状态码 + 空格」前缀(如 "请求超时（>60s）"
 * 或 "TypeError: Failed to fetch"):前者不含空格,整句原样返回;后者会截掉
 * 第一个词。两者都不在映射表里,落到 worldErrorMessage 的兜底「操作失败：…」,不崩。
 */
export function apiDetail(err: unknown): string {
	if (err instanceof ApiError) {
		const i = err.message.indexOf(' ');
		return i === -1 ? err.message : err.message.slice(i + 1);
	}
	return String(err);
}
