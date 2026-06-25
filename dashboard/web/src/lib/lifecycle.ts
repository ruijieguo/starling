// Phase 3 片 4 — 生命周期(Lifecycle)纯逻辑:占用快照 → 比例段 + 事件派生流转。
// 抽出来便于单测;/lifecycle 页只做渲染。consolidation_state / event_type 对齐 DB(小写串)。

export type Tone = 'neutral' | 'brand' | 'success' | 'warn' | 'danger' | 'info';
export type Occupancy = Record<string, number>;
export type Events = Record<string, number>;

// 生命周期阶段(按记忆流排序;DB consolidation_state 小写)。
const STAGES: { key: string; label: string; tone: Tone }[] = [
	{ key: 'volatile', label: '短期 · 海马', tone: 'info' },
	{ key: 'replaying_consolidating', label: '固化中', tone: 'brand' },
	{ key: 'consolidated', label: '长期 · 新皮层', tone: 'success' },
	{ key: 'archived', label: '归档', tone: 'neutral' },
	{ key: 'forgotten', label: '遗忘', tone: 'danger' }
];

// 占用快照(精确)→ 每阶段 {count, pct};总数 0 时 pct 全 0(空态由页面处理)。
export function occupancyStages(occ: Occupancy) {
	const total = STAGES.reduce((s, st) => s + (occ[st.key] ?? 0), 0);
	return {
		total,
		stages: STAGES.map((st) => {
			const count = occ[st.key] ?? 0;
			return { ...st, count, pct: total ? (count / total) * 100 : 0 };
		})
	};
}

// 流转(累计):多数从 typed bus 事件派生;遗忘无事件(forget 直接 UPDATE)→ 取占用快照。
export type Flow = {
	key: string;
	label: string;
	target: string; // 目标阶段 key
	count: number;
	source: 'event' | 'snapshot';
};

export function transitionFlows(ev: Events, occ: Occupancy): Flow[] {
	const consolidated = (ev['statement.consolidated'] ?? 0) + (ev['statement.consolidation_forced'] ?? 0);
	return [
		{ key: 'written', label: '摄入', target: 'volatile', count: ev['statement.written'] ?? 0, source: 'event' },
		{ key: 'consolidated', label: '固化', target: 'consolidated', count: consolidated, source: 'event' },
		{ key: 'archived', label: '归档', target: 'archived', count: ev['statement.archived'] ?? 0, source: 'event' },
		{ key: 'forgotten', label: '遗忘', target: 'forgotten', count: occ['forgotten'] ?? 0, source: 'snapshot' },
		{ key: 'derived', label: '派生', target: 'consolidated', count: ev['statement.derived'] ?? 0, source: 'event' },
		{ key: 'superseded', label: '取代', target: 'archived', count: ev['statement.superseded'] ?? 0, source: 'event' }
	];
}

// 固化通道是否已被驱动:有 consolidated 事件 → 已动;否则页面提示 SLEEP/IDLE 回放未接通。
export function consolidationDriven(ev: Events): boolean {
	return ((ev['statement.consolidated'] ?? 0) + (ev['statement.consolidation_forced'] ?? 0)) > 0;
}

// 目标阶段 key → 中文标签(流转行用)。未知兜底原 key。
export function stageLabel(key: string): string {
	return STAGES.find((s) => s.key === key)?.label ?? key;
}
