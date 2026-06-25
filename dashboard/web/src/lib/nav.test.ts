import { describe, it, expect } from 'vitest';
import { NAV_GROUPS } from './nav';

// Phase 3 片 1 — 类脑 IA 重组(经 plan-design-review 定稿)。
describe('NAV_GROUPS — 类脑 IA', () => {
	const allHrefs = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href));

	it('has 10 groups in memory-flow order, 透视镜 landed between 回放 and 脑干', () => {
		expect(NAV_GROUPS.map((g) => g.title)).toEqual([
			'总览',
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

	it('orphans no existing route in the reorg', () => {
		for (const href of [
			'/', '/converse', '/interact', '/working-set', '/statements', '/cognizers',
			'/commitments', '/reminders', '/replay', '/lifecycle', '/conflicts', '/vitals',
			'/queues', '/eval', '/settings'
		]) {
			expect(allHrefs).toContain(href);
		}
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
