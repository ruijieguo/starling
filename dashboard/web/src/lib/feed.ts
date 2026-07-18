// T7 — 概览「最近活动」feed 的事件结构化。
//
// 原先是 `JSON.stringify(payload).slice(0, 80)` 裸截断:用户看到的是被腰斩的 JSON
// 而非「发生了什么」。这里按事件类型渲染成一句人话 + 语义色,类型与 payload 形状
// 全部对齐后端 `routes/commands.py` 的 `_broadcast(kind, payload)` 实际发送值:
//
//   tick                   {embedded, fired, broken, auto_withdrawn,
//                           replay_sampled, consolidated, ttl_archived, stages[]}
//   statement_added        {statement_ids: string[]}
//   recall                 {n: number}
//   commitment_fired       {fired: number}
//   commitment_transition  {stmt_id, state}
//   statement_forgotten    {forgotten: number}
//
// 未知类型/缺字段一律优雅回退(只读面板,不因后端加事件或改 payload 而崩)。

export type FeedTone = 'neutral' | 'brand' | 'success' | 'warn' | 'danger' | 'info';

export type FeedEventView = {
	/** 事件类型的中文短标签(Badge 文案)。 */
	label: string;
	/** 一句话描述发生了什么;无可述细节时为空串(调用方可省略该行)。 */
	detail: string;
	tone: FeedTone;
};

const num = (v: unknown): number | null =>
	typeof v === 'number' && Number.isFinite(v) ? v : null;

/** tick 的各计数字段 → 「嵌入 3 · 固化 2」这样的摘要;全 0/缺失 → 空闲。 */
function describeTick(p: Record<string, unknown>): string {
	const parts: string[] = [];
	const add = (key: string, zh: string) => {
		const n = num(p[key]);
		if (n && n > 0) parts.push(`${zh} ${n}`);
	};
	add('embedded', '嵌入');
	add('consolidated', '固化');
	add('replay_sampled', '重放采样');
	add('fired', '触发承诺');
	add('broken', '违约');
	add('auto_withdrawn', '自动撤回');
	add('ttl_archived', '到期归档');
	return parts.length ? parts.join(' · ') : '空转(无待办)';
}

export function describeEvent(type: string, payload: unknown): FeedEventView {
	const p = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
	switch (type) {
		case 'tick': {
			const detail = describeTick(p);
			// 违约/自动撤回是需要注意的后台结果,给 warn;其余后台推进用中性。
			const alarming = (num(p.broken) ?? 0) > 0 || (num(p.auto_withdrawn) ?? 0) > 0;
			return { label: '后台 tick', detail, tone: alarming ? 'warn' : 'neutral' };
		}
		case 'statement_added': {
			const ids = Array.isArray(p.statement_ids) ? p.statement_ids : [];
			return {
				label: '新增语句',
				detail: ids.length ? `落库 ${ids.length} 条` : '落库(数量未知)',
				tone: 'success'
			};
		}
		case 'recall': {
			const n = num(p.n);
			return { label: '检索', detail: n === null ? '' : `召回 ${n} 条`, tone: 'info' };
		}
		case 'commitment_fired': {
			const n = num(p.fired);
			return { label: '承诺触发', detail: n === null ? '' : `${n} 条到期`, tone: 'warn' };
		}
		case 'commitment_transition': {
			const state = typeof p.state === 'string' ? p.state : '';
			const sid = typeof p.stmt_id === 'string' ? p.stmt_id : '';
			const short = sid ? `${sid.slice(0, 8)}…` : '';
			return {
				label: '承诺流转',
				detail: [short, state].filter(Boolean).join(' → '),
				// FULFILLED 是好结果,WITHDRAWN/BROKEN 值得留意。
				tone: state === 'FULFILLED' ? 'success' : state ? 'warn' : 'neutral'
			};
		}
		case 'statement_forgotten': {
			const n = num(p.forgotten);
			return { label: '遗忘', detail: n === null ? '' : `${n} 条移出检索`, tone: 'danger' };
		}
		default:
			// 后端新增事件类型时不崩:显示原类型名,细节留空。
			return { label: type || '事件', detail: '', tone: 'neutral' };
	}
}
