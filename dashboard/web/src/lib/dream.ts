// Phase 3 片 2 — 梦境日志(Dream Log)的纯逻辑:回放批次的模式标签 + ops 摘要。
// 抽出来便于单测;/replay 页只做渲染。replay_ledger.mode 在 DB 存小写。

export type LedgerRow = {
	replay_batch_id: string;
	mode: string; // online | idle | sleep
	sampled_count: number;
	ops_applied_json: string; // JSON object: { op_compress: 3, ... }(默认 '{}')
	started_at: string;
	finished_at: string | null;
};

type Mode = { label: string; tone: 'neutral' | 'info' | 'brand' };
const MODE: Record<string, Mode> = {
	online: { label: '在线', tone: 'neutral' }, // tick_online,事件触发的随手固化
	idle: { label: '空闲', tone: 'info' }, // run_idle(今无调用方)
	sleep: { label: '睡眠', tone: 'brand' } // run_sleep(今无调用方)
};

export function modeLabel(mode: string): Mode {
	return MODE[mode] ?? { label: mode || '未知', tone: 'neutral' };
}

const OP_LABEL: Record<string, string> = {
	op_compress: '固化',
	op_archive: '归档',
	op_prune: '修剪',
	op_promote: '晋升',
	op_reweight: '重权'
};

// "固化 3 · 归档 1";空对象 → "无操作";坏 JSON → "—"。未知 op 用原 key。
export function opsSummary(ops_applied_json: string): string {
	let ops: Record<string, number>;
	try {
		ops = JSON.parse(ops_applied_json || '{}');
	} catch {
		return '—';
	}
	const parts = Object.entries(ops)
		.filter(([, n]) => typeof n === 'number' && n > 0)
		.map(([k, n]) => `${OP_LABEL[k] ?? k} ${n}`);
	return parts.length ? parts.join(' · ') : '无操作';
}

// 是否已有空闲/睡眠批次(否则该叙事未接通,页面诚实标注)。
export function hasSleepOrIdle(rows: Pick<LedgerRow, 'mode'>[]): boolean {
	return rows.some((r) => r.mode === 'idle' || r.mode === 'sleep');
}
