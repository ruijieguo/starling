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
	last_updated_at: { label: '更新于', order: 44 },

	// ── T6 statements detail drawer 字段(/api/statements 的 15 列,见
	// python/starling/dashboard/queries.py::statements)。subject_kind / provenance /
	// derived_depth 目前不在该 SELECT 里,先备好标签:后端补列即自动归位到对应分区。
	// 注意 `id` 是通用列名,这里按「语句」语义命名——目前唯一另一个会把 `id` 喂给
	// labelFor 的消费者是 replay 页,而它显式 filter 掉了 `id`,故无误标风险。
	// order 对本批键是装饰性的:drawer 分区顺序由 sectionize 的 zone.keys 声明序决定,
	// 不读 order(order 只服务 orderedEntries 的消费者:overview/queues/replay 网格)。
	id: { label: '语句 ID', order: 50, gloss: '语句主键;批准 / 遗忘 / 透视等干预动作以它为准' },
	holder_id: { label: '持有者', order: 51, gloss: '持有这条判断的认知体;self 即记忆体自身' },
	holder_perspective: {
		label: '持有视角',
		order: 52,
		// 取信途径(非人称):first_person 亲身持有,其余三值是转手得来的信息。
		// 「我以为他信 X」是 nesting_depth ≥ 1 的语义,与本字段正交,勿混。
		gloss: 'first_person = 记忆体亲身持有;quoted / inferred / hearsay = 引述 / 推断 / 传闻得来'
	},
	subject_kind: { label: '主语类型', order: 53, gloss: 'cognizer(认知体)或 entity(实体)' },
	subject_id: { label: '主语', order: 54 },
	predicate: { label: '谓词', order: 55 },
	object_kind: { label: '宾语类型', order: 56 },
	object_value: { label: '宾语', order: 57 },
	modality: {
		label: '模态',
		order: 58,
		// 12 值分四类(believes/knows/assumes/doubts 信念;desires/intends/commits/prefers
		// 意图;norm_ought/norm_forbid 规范;occurred 事件;recanted 已撤回)。
		gloss: '信念(believes/knows/assumes/doubts)· 意图(desires/intends/commits/prefers)· 规范(norm_ought/norm_forbid)· 事件(occurred)· 撤回(recanted)'
	},
	polarity: { label: '极性', order: 59, gloss: 'pos 肯定 / neg 否定 / unknown 未定' },
	confidence: { label: '置信度', order: 60, gloss: '记忆体对这条判断的确信程度' },
	salience: { label: '显著度', order: 61, gloss: '影响检索排序与衰减速度' },
	consolidation_state: {
		label: '固化态',
		order: 62,
		gloss: '易逝(海马)→ 回放固化 → 已固化(新皮层)'
	},
	review_status: { label: '审批状态', order: 63, gloss: 'review_requested 即落入人工审批队列' },
	nesting_depth: {
		label: '信念阶层',
		order: 64,
		gloss: '0 = 一阶(我信 X);≥1 = 二阶及以上(我以为你信 X)'
	},
	provenance: { label: '来源', order: 65, gloss: '这条语句的产生途径,如直接摄入 / 固化抽象' },
	derived_depth: { label: '派生深度', order: 66, gloss: '距离原始观察经过了几层派生' },
	observed_at: { label: '观察于', order: 67, gloss: '这条判断被观察 / 写入的时刻' },

	// ── T6 commitments detail drawer 字段(/api/commitments 的 9 列 + 前端派生的 fired)。
	stmt_id: { label: '承诺语句 ID', order: 80, gloss: '承诺挂靠的语句主键' },
	state: {
		label: '状态',
		order: 81,
		gloss: 'created → ACTIVE → 终态(FULFILLED / BROKEN / RENEGOTIATED / WITHDRAWN)'
	},
	broken_count: { label: '违约次数', order: 82, gloss: '累计违约次数;≥3 可能已被后台自动撤回' },
	fired: { label: '到期触发', order: 83, gloss: '存在已 fired 的触发器(看板上的 ⚠ DUE)' },
	deadline: { label: '截止时间', order: 84 },
	created_at: { label: '创建于', order: 85 },
	updated_at: { label: '更新于', order: 86 }
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

/** 一个分区规格:中文小标题 + 该区收编的 key(呈现顺序即声明顺序,而非 SQL 列序)。 */
export type ZoneSpec = { title: string; keys: readonly string[] };
/** 一个分区的呈现结果:小标题 + 该记录里实际存在的条目。 */
export type Section<T> = { title: string; entries: [string, T][] };

/**
 * T6 —— 把一条明细记录切成分区呈现,替代 detail drawer 里的裸 `Object.entries` dump。
 *
 * - 每区只保留记录里**实际存在**的 key(zone 可以预声明后端还没返回的列,不会渲染空行);
 * - 同一 key 被多区声明时先声明者胜,绝不重复呈现;
 * - 所有分区都没收编的 key 落进兜底区 `restTitle` —— **不丢字段**是硬不变式:
 *   后端新增列时它自动出现在兜底区,而不是被静默吞掉;
 * - 空区不产出,避免渲染只有标题的空分区。
 */
export function sectionize<T>(
	obj: Record<string, T> | null | undefined,
	zones: readonly ZoneSpec[],
	restTitle = '其它'
): Section<T>[] {
	if (!obj) return [];
	const own = new Set(Object.keys(obj)); // 自有 key,避免 `in` 命中原型链
	const claimed = new Set<string>();
	const sections: Section<T>[] = [];
	for (const zone of zones) {
		const entries: [string, T][] = [];
		for (const key of zone.keys) {
			if (!own.has(key) || claimed.has(key)) continue;
			claimed.add(key);
			entries.push([key, obj[key]]);
		}
		if (entries.length) sections.push({ title: zone.title, entries });
	}
	const rest = Object.entries(obj).filter(([k]) => !claimed.has(k));
	if (rest.length) sections.push({ title: restTitle, entries: rest });
	return sections;
}
