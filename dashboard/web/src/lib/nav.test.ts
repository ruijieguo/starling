import { describe, it, expect } from 'vitest';
import { NAV_GROUPS } from './nav';

// Phase 3 片 1 — 类脑 IA 重组(经 plan-design-review 定稿)。
describe('NAV_GROUPS — 类脑 IA', () => {
	const allHrefs = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href));

	it('has 11 groups in memory-flow order, 原始数据·证据 landed between 总览 and 对话', () => {
		expect(NAV_GROUPS.map((g) => g.title)).toEqual([
			'总览',
			'原始数据 · 证据',
			'对话',
			'短期记忆 · 海马',
			'长期记忆 · 新皮层',
			'他者心智 · 心智化',
			'意图与承诺 · 前额叶',
			'睡眠与固化 · 回放',
			'透视镜',
			'生命体征 · 脑干',
			'配置'
		]);
	});

	it('surfaces /brain as the landing home', () => {
		expect(allHrefs).toContain('/brain');
	});

	it('surfaces /lens now that slice 3 landed (透视镜 un-dormanted)', () => {
		expect(allHrefs).toContain('/lens');
	});

	it('surfaces /engrams (T0a — 原始数据·证据, un-dormanted)', () => {
		expect(allHrefs).toContain('/engrams');
	});

	it('orphans no existing route in the reorg', () => {
		for (const href of [
			'/', '/converse', '/interact', '/working-set', '/statements', '/cognizers',
			'/commitments', '/reminders', '/replay', '/lifecycle', '/forecast', '/conflicts',
			'/vitals', '/queues', '/eval', '/settings', '/engrams'
		]) {
			expect(allHrefs).toContain(href);
		}
	});

	it('includes /runtime-health in 生命体征 · 脑干 group', () => {
		expect(allHrefs).toContain('/runtime-health');
		const brainStemGroup = NAV_GROUPS.find((g) => g.title === '生命体征 · 脑干');
		expect(brainStemGroup).toBeDefined();
		const item = brainStemGroup!.items.find((i) => i.href === '/runtime-health');
		expect(item).toBeDefined();
		expect(item!.label).toBe('运行时健康');
		expect(item!.icon).toBeTruthy();
	});

	it('every item has a label and icon', () => {
		for (const g of NAV_GROUPS) {
			for (const i of g.items) {
				expect(i.label).toBeTruthy();
				expect(i.icon).toBeTruthy();
			}
		}
	});
});
