// Vitals (Phase 0 read-only observability) — response types + tone helper.
// lag is a GLOBAL signal (MAX(outbox_sequence) − each pump's checkpoint cursor);
// the lifecycle blocks below are tenant-scoped server-side. See
// python/starling/dashboard/queries.py:vitals.

export type VitalsLag = {
	pump: string;
	ok: boolean; // false → checkpoint table absent (migration not run)
	cursor: number | null;
	head: number;
	lag: number | null;
};

export type VolatileStuck = {
	id: string;
	subject_id: string;
	predicate: string;
	object_value: string;
	salience: number;
	replay_count: number;
	consolidation_state: string;
	created_at: string;
	observed_at: string;
	last_replayed: string | null;
};

export type ExtractionFailure = {
	id: string;
	pipeline_run_id: string;
	extraction_span_key: string;
	attempt_number: number;
	status: string;
	error: string | null;
	raw_output: string | null;
	created_at: string;
};

export type OverdueWindow = {
	stmt_id: string;
	opened_at: string;
	close_deadline: string;
	status: string;
};

// 历史成本(0027):租户级 token 用量 + 时延汇总。成本只在适配器(核心)采集,
// 这里只读聚合;fake/未采集端点 → 0(诚实「无成本数据」,非缺失)。
export type ExtractionCost = {
	attempts: number;
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	latency_ms: number;
};

// 近 N 次 pipeline_run 的逐次成本(按 run 汇总,DESC by started_at)。
export type ExtractionCostRun = ExtractionCost & {
	run_id: string;
	started_at: string | null;
};

export type VitalsResponse = {
	outbox_head: number;
	max_lag: number;
	lag: VitalsLag[];
	volatile_stuck: VolatileStuck[];
	volatile_stuck_total: number;
	extraction_failures: ExtractionFailure[];
	extraction_failures_total: number;
	extraction_cost: ExtractionCost;
	extraction_cost_runs: ExtractionCostRun[];
	overdue_windows: OverdueWindow[];
	overdue_windows_total: number;
};

export type LagTone = 'success' | 'warn' | 'danger' | 'unknown';

// Health of one pump's lag. null lag = the checkpoint table is missing (not a
// crash — a missing migration), surfaced as 'unknown' rather than fake-green.
export function lagTone(lag: number | null): { tone: LagTone; label: string } {
	if (lag === null) return { tone: 'unknown', label: '无 checkpoint' };
	if (lag === 0) return { tone: 'success', label: '健康' };
	if (lag <= 20) return { tone: 'warn', label: '滞后' };
	return { tone: 'danger', label: '高滞后' };
}

// Headline "all healthy" affirmative state: every pump caught up AND nothing
// stuck. Drives the calm reassurance empty-state instead of a blank page.
export function allHealthy(v: VitalsResponse): boolean {
	return (
		v.max_lag === 0 &&
		v.volatile_stuck_total === 0 &&
		v.extraction_failures_total === 0 &&
		v.overdue_windows_total === 0
	);
}
