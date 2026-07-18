import { describe, expect, it } from 'vitest';
import { describeEvent } from './feed';

describe('describeEvent — 概览 feed 事件结构化', () => {
	it('tick: 只列非零计数,按后端字段名对齐', () => {
		const v = describeEvent('tick', {
			embedded: 3,
			consolidated: 2,
			replay_sampled: 0,
			fired: 0,
			broken: 0,
			auto_withdrawn: 0,
			ttl_archived: 0
		});
		expect(v.label).toBe('后台 tick');
		expect(v.detail).toBe('嵌入 3 · 固化 2');
		expect(v.tone).toBe('neutral');
	});

	it('tick: 全零 → 空转文案(而非空白)', () => {
		expect(describeEvent('tick', { embedded: 0, consolidated: 0 }).detail).toBe('空转(无待办)');
		expect(describeEvent('tick', {}).detail).toBe('空转(无待办)');
	});

	it('tick: 违约/自动撤回 → warn(值得注意的后台结果)', () => {
		expect(describeEvent('tick', { broken: 1 }).tone).toBe('warn');
		expect(describeEvent('tick', { auto_withdrawn: 2 }).tone).toBe('warn');
		expect(describeEvent('tick', { embedded: 5 }).tone).toBe('neutral');
	});

	it('statement_added: 用 statement_ids 长度', () => {
		const v = describeEvent('statement_added', { statement_ids: ['a', 'b', 'c'] });
		expect(v.label).toBe('新增语句');
		expect(v.detail).toBe('落库 3 条');
		expect(v.tone).toBe('success');
	});

	it('recall / commitment_fired / statement_forgotten: 各自的计数字段', () => {
		expect(describeEvent('recall', { n: 7 }).detail).toBe('召回 7 条');
		expect(describeEvent('commitment_fired', { fired: 2 }).detail).toBe('2 条到期');
		expect(describeEvent('statement_forgotten', { forgotten: 4 }).detail).toBe('4 条移出检索');
		expect(describeEvent('statement_forgotten', { forgotten: 4 }).tone).toBe('danger');
	});

	it('commitment_transition: 短 id + 目标态,FULFILLED 为 success', () => {
		const v = describeEvent('commitment_transition', {
			stmt_id: '0123456789abcdef',
			state: 'FULFILLED'
		});
		expect(v.detail).toBe('01234567… → FULFILLED');
		expect(v.tone).toBe('success');
		expect(describeEvent('commitment_transition', { stmt_id: 'x', state: 'WITHDRAWN' }).tone).toBe(
			'warn'
		);
	});

	it('未知类型 / 脏 payload 一律优雅回退,不崩', () => {
		expect(describeEvent('brand_new_event', { whatever: 1 })).toEqual({
			label: 'brand_new_event',
			detail: '',
			tone: 'neutral'
		});
		// payload 非对象 / null / 缺字段
		expect(describeEvent('recall', null).detail).toBe('');
		expect(describeEvent('recall', 'garbage').detail).toBe('');
		expect(describeEvent('statement_added', {}).detail).toBe('落库(数量未知)');
		// 非有限数不当作计数
		expect(describeEvent('recall', { n: NaN }).detail).toBe('');
		expect(describeEvent('tick', { embedded: 'x' }).detail).toBe('空转(无待办)');
	});
});
