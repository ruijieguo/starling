import { describe, it, expect } from 'vitest';
import { labelFor, glossFor, orderedEntries, sectionize } from './labels';

describe('labels (T5 友好标签 + 策展呈现)', () => {
	it('labelFor: known keys map to Chinese friendly names', () => {
		expect(labelFor('statements')).toBe('语句');
		expect(labelFor('statement_edges')).toBe('关系边');
		expect(labelFor('cognizers')).toBe('认知体');
		expect(labelFor('commitments')).toBe('承诺');
		expect(labelFor('bus_events')).toBe('总线事件');
		expect(labelFor('ACTIVE')).toBe('生效中');
		expect(labelFor('pending')).toBe('待派发');
		expect(labelFor('embedded')).toBe('已嵌入');
		expect(labelFor('last_updated_at')).toBe('更新于');
	});

	it('labelFor: unknown key falls back to the raw key (never throws)', () => {
		expect(labelFor('some_new_backend_key')).toBe('some_new_backend_key');
		expect(labelFor('')).toBe('');
	});

	it('glossFor: returns gloss for entries that have one, undefined otherwise', () => {
		expect(glossFor('statements')).toBe('新皮层长期记忆的原子命题总数');
		expect(glossFor('ACTIVE')).toBeUndefined(); // no gloss defined
		expect(glossFor('unknown_key')).toBeUndefined();
	});

	it('orderedEntries: sorts known keys by curated weight regardless of input order', () => {
		const input = { bus_events: 4, statements: 1, cognizers: 2 };
		expect(orderedEntries(input).map(([k]) => k)).toEqual(['statements', 'cognizers', 'bus_events']);
	});

	it('orderedEntries: preserves values alongside sorted keys', () => {
		const input = { commitments: 7, statements: 3 };
		expect(orderedEntries(input)).toEqual([
			['statements', 3],
			['commitments', 7]
		]);
	});

	it('orderedEntries: unknown keys land after known keys, preserving relative order', () => {
		const input = { mystery_b: 2, statements: 1, mystery_a: 3, cognizers: 4 };
		expect(orderedEntries(input).map(([k]) => k)).toEqual([
			'statements',
			'cognizers',
			'mystery_b',
			'mystery_a'
		]);
	});

	it('orderedEntries: all-unknown object keeps input order, no crash', () => {
		const input = { foo: 1, bar: 2 };
		expect(orderedEntries(input)).toEqual([
			['foo', 1],
			['bar', 2]
		]);
	});

	it('orderedEntries: null/undefined input → empty array (defensive)', () => {
		expect(orderedEntries(null)).toEqual([]);
		expect(orderedEntries(undefined)).toEqual([]);
	});

	it('orderedEntries: empty object → empty array', () => {
		expect(orderedEntries({})).toEqual([]);
	});

	it('orderedEntries: commitment states sort in the six-state machine order', () => {
		const input = {
			WITHDRAWN: 1,
			created: 2,
			BROKEN: 3,
			ACTIVE: 4,
			FULFILLED: 5,
			RENEGOTIATED: 6
		};
		expect(orderedEntries(input).map(([k]) => k)).toEqual([
			'created',
			'ACTIVE',
			'FULFILLED',
			'BROKEN',
			'RENEGOTIATED',
			'WITHDRAWN'
		]);
	});
});

describe('labels — T6 detail drawer 字段名', () => {
	it('labelFor: statement 字段(/api/statements 的 15 列)全部有中文标签', () => {
		// 这 15 个 key 就是 queries.py::statements 的 SELECT 列;任何一个漏进字典,
		// drawer 就会退回裸 DB 列名当标签 —— 正是 T6 要消除的现象。
		const columns = [
			'id',
			'holder_id',
			'holder_perspective',
			'subject_id',
			'predicate',
			'object_kind',
			'object_value',
			'modality',
			'polarity',
			'confidence',
			'salience',
			'observed_at',
			'review_status',
			'consolidation_state',
			'nesting_depth'
		];
		for (const key of columns) expect(labelFor(key), `${key} 未进字典`).not.toBe(key);
		expect(labelFor('holder_id')).toBe('持有者');
		expect(labelFor('modality')).toBe('模态');
		expect(labelFor('consolidation_state')).toBe('固化态');
		expect(labelFor('nesting_depth')).toBe('信念阶层');
		expect(labelFor('observed_at')).toBe('观察于');
	});

	it('labelFor: 后端尚未返回但已备好标签的 statement 列', () => {
		expect(labelFor('subject_kind')).toBe('主语类型');
		expect(labelFor('provenance')).toBe('来源');
		expect(labelFor('derived_depth')).toBe('派生深度');
	});

	it('labelFor: commitment 字段(含前端派生的 fired)全部有中文标签', () => {
		const columns = [
			'stmt_id',
			'state',
			'broken_count',
			'deadline',
			'created_at',
			'updated_at',
			'subject_id',
			'predicate',
			'object_value',
			'fired'
		];
		for (const key of columns) expect(labelFor(key), `${key} 未进字典`).not.toBe(key);
		expect(labelFor('broken_count')).toBe('违约次数');
		expect(labelFor('stmt_id')).toBe('承诺语句 ID');
		expect(labelFor('state')).toBe('状态');
		expect(labelFor('deadline')).toBe('截止时间');
	});

	it('glossFor: 语义重的字段带悬浮说明,轻字段不强凑', () => {
		expect(glossFor('nesting_depth')).toContain('一阶');
		expect(glossFor('consolidation_state')).toContain('新皮层');
		expect(glossFor('broken_count')).toContain('自动撤回');
		expect(glossFor('deadline')).toBeUndefined(); // 字面意思,不需要 gloss
	});

	it('新增字段没有覆盖 T5 已有的 overview / queues / replay 标签', () => {
		expect(labelFor('statements')).toBe('语句');
		expect(labelFor('commitments')).toBe('承诺');
		expect(labelFor('created')).toBe('已创建');
		expect(labelFor('ACTIVE')).toBe('生效中');
		expect(labelFor('last_updated_at')).toBe('更新于');
	});
});

describe('sectionize (T6 detail drawer 分区)', () => {
	const ZONES = [
		{ title: '核心', keys: ['subject_id', 'predicate'] },
		{ title: '元数据', keys: ['confidence'] }
	];

	it('按 zone 声明顺序分区,而非对象自身的 key 顺序', () => {
		const detail = { confidence: 0.9, predicate: 'likes', subject_id: 'alice' };
		expect(sectionize(detail, ZONES)).toEqual([
			{ title: '核心', entries: [['subject_id', 'alice'], ['predicate', 'likes']] },
			{ title: '元数据', entries: [['confidence', 0.9]] }
		]);
	});

	it('zone 声明了但记录里没有的 key 直接跳过(不渲染空行)', () => {
		const detail = { subject_id: 'alice' };
		expect(sectionize(detail, ZONES)).toEqual([
			{ title: '核心', entries: [['subject_id', 'alice']] }
		]);
	});

	it('空区不产出,避免只有标题的空分区', () => {
		expect(sectionize({ confidence: 1 }, ZONES).map((s) => s.title)).toEqual(['元数据']);
	});

	it('任何 zone 都没收编的 key 落进兜底区,保留原相对顺序', () => {
		const detail = { subject_id: 'alice', zeta: 1, alpha: 2 };
		const sections = sectionize(detail, ZONES);
		expect(sections.at(-1)).toEqual({
			title: '其它',
			entries: [['zeta', 1], ['alpha', 2]]
		});
	});

	it('兜底区标题可自定义', () => {
		expect(sectionize({ mystery: 1 }, ZONES, '未分类')[0].title).toBe('未分类');
	});

	it('不丢字段:分区后条目集合与输入完全一致(硬不变式)', () => {
		// 后端新增列 / 前端派生字段都必须仍然可见 —— 这是 T6 的核心约束。
		const detail = {
			subject_id: 'alice',
			predicate: 'likes',
			confidence: 0.9,
			brand_new_backend_column: 'x',
			fired: true
		};
		const flat = sectionize(detail, ZONES).flatMap((s) => s.entries);
		expect(Object.fromEntries(flat)).toEqual(detail);
		expect(flat).toHaveLength(Object.keys(detail).length);
	});

	it('key 被多区声明时先声明者胜,绝不重复呈现', () => {
		const dupZones = [
			{ title: 'A', keys: ['predicate'] },
			{ title: 'B', keys: ['predicate', 'confidence'] }
		];
		const sections = sectionize({ predicate: 'likes', confidence: 1 }, dupZones);
		expect(sections).toEqual([
			{ title: 'A', entries: [['predicate', 'likes']] },
			{ title: 'B', entries: [['confidence', 1]] }
		]);
	});

	it('null / undefined / 空记录 → 空数组(防御)', () => {
		expect(sectionize(null, ZONES)).toEqual([]);
		expect(sectionize(undefined, ZONES)).toEqual([]);
		expect(sectionize({}, ZONES)).toEqual([]);
	});

	it('zones 为空时全部字段落进兜底区(仍不丢字段)', () => {
		expect(sectionize({ a: 1, b: 2 }, [])).toEqual([
			{ title: '其它', entries: [['a', 1], ['b', 2]] }
		]);
	});

	it('不把原型链上的属性误当作自有字段', () => {
		const sections = sectionize({ subject_id: 'alice' }, [
			{ title: '核心', keys: ['subject_id', 'toString', 'constructor'] }
		]);
		expect(sections).toEqual([{ title: '核心', entries: [['subject_id', 'alice']] }]);
	});
});
