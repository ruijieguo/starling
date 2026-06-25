import { getToken } from './token';

export class ApiError extends Error {
	constructor(
		public status: number,
		public path: string,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
	/** 401/403 → 多半是 token 缺失/失效。 */
	get isAuth(): boolean {
		return this.status === 401 || this.status === 403;
	}
}

const TIMEOUT_MS = 15000;

// 默认 15s 适用于本地读查询;走 LLM/embedder 网络的端点(remember/recall/
// working_set/config test/save/tick)真模型下要 20-45s 甚至更久,调用点用
// timeoutMs 按请求放宽——否则前端先报超时、后端继续完成,UI 与事实错位。
type ReqInit = RequestInit & { timeoutMs?: number };

async function req<T>(path: string, init: ReqInit = {}): Promise<T> {
	const { timeoutMs = TIMEOUT_MS, ...rest } = init;
	const headers = new Headers(rest.headers);
	const tok = getToken();
	if (tok) headers.set('Authorization', `Bearer ${tok}`);
	headers.set('Content-Type', 'application/json');
	const ctrl = new AbortController();
	const timer = setTimeout(() => ctrl.abort(), timeoutMs);
	// caller 传入的 signal 链到内部 controller:保证超时始终生效,且 caller 取消也能传播。
	if (rest.signal) {
		if (rest.signal.aborted) ctrl.abort();
		else rest.signal.addEventListener('abort', () => ctrl.abort(), { once: true });
	}
	try {
		const res = await fetch(path, { ...rest, headers, signal: ctrl.signal });
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				if (body?.detail) detail = String(body.detail);
			} catch {
				/* 非 JSON body,保留 statusText */
			}
			throw new ApiError(res.status, path, `${res.status} ${detail}`);
		}
		return (await res.json()) as T;
	} catch (e) {
		if (e instanceof ApiError) throw e;
		if (e instanceof DOMException && e.name === 'AbortError')
			throw new ApiError(0, path, `请求超时（>${timeoutMs / 1000}s）`);
		throw new ApiError(0, path, String(e));
	} finally {
		clearTimeout(timer);
	}
}

export const api = {
	get: <T>(p: string, init?: ReqInit) => req<T>(p, init),
	post: <T>(p: string, body: unknown, init?: ReqInit) =>
		req<T>(p, { ...init, method: 'POST', body: JSON.stringify(body) }),
	del: <T>(p: string, init?: ReqInit) => req<T>(p, { ...init, method: 'DELETE' })
};

// 归因 receipt(Phase 0 起 plan_query 纯增量带出;runtime_health 不暴露)。
export type RecallReceipt = {
	trace_id: string;
	query_id: string;
	sufficiency_status: string;
	filters_applied: { name: string; value: string }[];
	candidate_counts: {
		fetched: number;
		returned: number;
		dropped_by_review: number;
		dropped_by_state: number;
		dropped_by_time_anchor: number;
		dropped_by_evidence_erasure: number;
	};
	frontier_masked_count: number;
	evidence_erased_count: number;
	projection_lag_events: number;
	degraded_paths: { path: string; reason: string; fallback: string }[];
	score_breakdown: {
		statement_id: string;
		base: number;
		recency: number;
		salience: number;
		activation: number;
		affect_consistency: number;
		temporal_penalty: number;
		final_score: number;
	}[];
	skipped_scopes: { scope: string; reason: string }[];
	stop_reason: string;
};

// P3.a1 检索规划响应(POST /api/recall 带 intent 时)。
export type PlannedRecallResponse = {
	results: { subject: string; predicate: string; object: string; score: number; label: string }[];
	context_pack: string;
	abstained: boolean;
	abstention_reason: string;
	plan_steps: { step: string; detail: string }[];
	scopes_searched: string[];
	receipt?: RecallReceipt; // 纯增量:旧 6 字段不变,归因细节新增于此
};

// Phase 2c 带记忆聊天一轮的响应(POST /api/converse)。
export type ConverseResponse = {
	reply: string;
	ok: boolean; // generate 成功 → 有回复
	error: string;
	context_pack: string; // 本轮注入的记忆(带标签)
	abstained: boolean;
	statement_ids: string[]; // 本轮沉淀的语句
	remember_ok: boolean; // false → 回复在但记忆未落库
	remember_error: string;
	// 2b 成本采集:本轮回复生成的 token/延迟(真模型填充,Fake/stub 为 0)。
	gen_prompt_tokens: number;
	gen_completion_tokens: number;
	gen_total_tokens: number;
	gen_latency_ms: number;
};

// Phase 3 片 3 — 透视镜(Lens)来源取证(GET /api/provenance/{id})。
export type ExtractionAttemptRow = {
	attempt_number: number | null;
	status: string | null;
	raw_output: string | null; // 原始 LLM 输出(仅失败/解析失败留底)
	error: string | null;
	created_at: string | null;
};

export type ExtractionAttempt = {
	span_key: string;
	status: string | null; // 权威行:success|partial_success|failed|noop(DB 无 CHECK)
	attempt_number: number | null;
	raw_output: string | null; // 权威行的 raw(成功路径通常 null)
	error: string | null;
	created_at: string | null;
	run_id: string | null;
	failed_attempts: ExtractionAttemptRow[]; // 同 run 失败/部分尝试(带原始 LLM 输出)
};

export type EngramEvidence = {
	engram_ref: string | null;
	content_hash: string | null;
	status: string | null;
	engram: {
		source_kind: string;
		privacy_class: string;
		created_at: string;
		erased: boolean;
		payload_preview: string | null; // 仅 inline 且未抹除取前 280 字符
	} | null;
};

// 递归节点:完整节点带 statement/origin/evidence/子树;折叠节点(repeat / found=false)只带 summary/id。
export type ProvenanceNode = {
	id: string;
	found: boolean; // false → 孤儿父 / 跨租户引用(只有 id)
	repeat?: boolean; // 已在上文展开(共享父 / 环)→ 不再递归
	summary?: { subject_id: string; predicate: string; object_value: string };
	statement?: Record<string, unknown>;
	origin?: { provenance: string; extraction: ExtractionAttempt | null };
	evidence?: EngramEvidence[];
	evidence_parse_error?: boolean;
	derived_from_parse_error?: boolean;
	derived_from?: ProvenanceNode[];
	supersedes?: ProvenanceNode | null;
	truncated?: boolean; // 到深度上限,更深来源未展开
};

// 透视镜取镜:只读文本查找(GET /api/statement_search)。
export type StatementSearchResponse = {
	rows: {
		id: string;
		holder_id: string;
		subject_id: string;
		predicate: string;
		object_value: string;
		consolidation_state: string;
		review_status: string;
		observed_at: string;
	}[];
	query: string;
};

// Phase 3 片 4 — 生命周期(GET /api/lifecycle):占用快照 + 事件派生流转(累计)。
export type LifecycleResponse = {
	occupancy: Record<string, number>; // consolidation_state → 当前条数(精确)
	events: Record<string, number>; // statement.* 事件 → 累计计数(事件派生)
};

// Phase 3 片 5 — 衰减预报(GET /api/forecast):C++ forgetting_curve 只读投影,排「最快被遗忘」。
export type ForecastRow = {
	id: string;
	subject_id: string;
	predicate: string;
	object_value: string;
	modality: string;
	salience: number;
	access_count: number;
	last_accessed: string;
	consolidation_state: string;
	active_grounded: boolean; // 受 ACTIVE commitment 保护 → 不会被 decay 归档
	s_t: number; // 当前 retrievability ∈ (0,1],升序排列(最低在前)
	forget_at: string | null; // 预计 S(t) 跌至 threshold 的时点;null=无投影/溢出
};
export type ForecastResponse = {
	rows: ForecastRow[];
	threshold: number; // 归档阈值(0.05,同 op_decay)
	now: string;
	candidate_limit: number; // 候选有界上限
};
