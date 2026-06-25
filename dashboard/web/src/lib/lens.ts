// Phase 3 片 3 — 透视镜(Lens)纯逻辑:extraction 状态标签 + 来源 gloss + 节点摘要。
// 抽出来便于单测;/lens 页只做渲染与递归。值域对齐 DB(小写串;status 无 CHECK→兜底)。

export type Tone = 'neutral' | 'brand' | 'success' | 'warn' | 'danger' | 'info';

// extraction_attempt.status:success | partial_success | failed | noop(DB 无 CHECK → 未知兜底原值)。
const STATUS: Record<string, { label: string; tone: Tone }> = {
	success: { label: '成功', tone: 'success' },
	partial_success: { label: '部分成功', tone: 'warn' },
	failed: { label: '失败', tone: 'danger' },
	noop: { label: '无操作', tone: 'neutral' }
};

export function statusLabel(s: string | null | undefined): { label: string; tone: Tone } {
	if (!s) return { label: '无抽取记录', tone: 'neutral' };
	return STATUS[s] ?? { label: s, tone: 'neutral' };
}

// statements.provenance 来源枚举(C++ to_string,小写)→ 中文 gloss(未知兜底原值)。
const ORIGIN: Record<string, string> = {
	user_input: '用户输入',
	tom_inferred: '心智推断',
	replay_derived: '回放派生',
	reconsolidation_derived: '再固化派生'
};

export function originLabel(p: string | null | undefined): string {
	if (!p) return '—';
	return ORIGIN[p] ?? p;
}

// 节点单行摘要 "subject · predicate · object"(折叠的派生/前身/repeat 节点用)。
// 完整节点读 statement,折叠节点(repeat / found=false 的补摘要)读 summary。
type Summ = { subject_id?: unknown; predicate?: unknown; object_value?: unknown };
export function nodeSummary(n: { statement?: Summ | null; summary?: Summ | null }): string {
	const s = n.statement ?? n.summary;
	if (!s) return '(未解析)';
	const parts = [s.subject_id, s.predicate, s.object_value]
		.map((x) => (x == null ? '' : String(x)))
		.filter(Boolean);
	return parts.length ? parts.join(' · ') : '(空)';
}
