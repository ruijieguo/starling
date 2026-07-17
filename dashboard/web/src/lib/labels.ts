// T5 友好标签 + 策展呈现 —— 后端 key → 中文友好名的单一字典。
// overview / queues / replay 三页原先 `Object.entries(obj)` 直接铺后端原始 key 当 label,
// 看着像自动生成;这里补一层「策展」:友好名 + 可选排序权重 + 可选 gloss(悬浮说明)。
// 未知 key(后端可能新增字典未覆盖的)优雅回退到原 key,绝不崩。

export type LabelEntry = {
	label: string;
	// 排序权重,数值越小越靠前;同一分组内按后端语义分组预留了间隔(10 的倍数起跳),
	// 便于以后插入新 key 而不用重排现有权重。
	order: number;
	gloss?: string;
};

const LABELS: Record<string, LabelEntry> = {
	// overview /api/overview → counts(记忆体核心计数)。
	statements: { label: '语句', order: 0, gloss: '新皮层长期记忆的原子命题总数' },
	statement_edges: { label: '关系边', order: 1, gloss: '语句之间的派生 / 矛盾等关系边' },
	cognizers: { label: '认知体', order: 2, gloss: '被建模的自我与他者心智数量' },
	commitments: { label: '承诺', order: 3, gloss: '前额叶跟踪的意图与承诺总数' },
	bus_events: { label: '总线事件', order: 4, gloss: '经内部事件总线派发的事件总数' },

	// overview /api/overview → commitments_by_state(承诺六态机,见 migrations/0018)。
	created: { label: '已创建', order: 10 },
	ACTIVE: { label: '生效中', order: 11 },
	FULFILLED: { label: '已履行', order: 12 },
	BROKEN: { label: '已违约', order: 13 },
	RENEGOTIATED: { label: '已重新协商', order: 14 },
	WITHDRAWN: { label: '已撤回', order: 15 },

	// overview /api/overview → queue_by_status 与 queues /api/queues → dispatch
	// (均为 bus_events.dispatch_status,见 migrations/0001)。
	pending: { label: '待派发', order: 20 },
	in_flight: { label: '派发中', order: 21 },
	delivered: { label: '已送达', order: 22 },
	dead_letter: { label: '死信', order: 23 },

	// queues /api/queues → vectors_by_status(statement_vectors.status,见 migrations/0016)。
	embedded: { label: '已嵌入', order: 30 },
	failed: { label: '失败', order: 31 },

	// replay /api/replay → scheduler(replay_scheduler_state,见 migrations/0011)。
	online_trigger_counter: { label: '在线触发计数', order: 40 },
	last_online_run_at: { label: '上次在线回放', order: 41 },
	last_idle_run_at: { label: '上次空闲回放', order: 42 },
	last_sleep_run_at: { label: '上次睡眠回放', order: 43 },
	last_updated_at: { label: '更新于', order: 44 }
};

/** 后端 key → 中文友好名;未知 key 回退到原 key(绝不崩)。 */
export function labelFor(key: string): string {
	return LABELS[key]?.label ?? key;
}

/** 后端 key → 可选 gloss(悬浮说明);未知 key 或无 gloss 返回 undefined。 */
export function glossFor(key: string): string | undefined {
	return LABELS[key]?.gloss;
}

/**
 * 按策展顺序排列 record 的条目,而非 API 返回顺序(常是 SQL GROUP BY 的任意顺序)。
 * 已知 key 按 order 权重升序排在前;未知 key(字典未覆盖)保持其在原对象里的相对顺序,
 * 整体排在已知 key 之后 —— 新 key 出现时既不丢失也不打乱已知布局。
 */
export function orderedEntries<T>(obj: Record<string, T> | null | undefined): [string, T][] {
	if (!obj) return [];
	const known: { entry: [string, T]; order: number }[] = [];
	const unknown: [string, T][] = [];
	for (const entry of Object.entries(obj)) {
		const meta = LABELS[entry[0]];
		if (meta) known.push({ entry, order: meta.order });
		else unknown.push(entry);
	}
	known.sort((a, b) => a.order - b.order);
	return [...known.map((k) => k.entry), ...unknown];
}
