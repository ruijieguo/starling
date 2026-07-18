import { describe, it, expect } from 'vitest';
import { NAV_GROUPS, matchesHref, activeNavItem } from './nav';

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
			expect(allHrefs.some((h) => h === href || h.startsWith(`${href}?`))).toBe(true);
		}
	});

	it('T0c — working-set moved into 对话 group', () => {
		const converseGroup = NAV_GROUPS.find((g) => g.title === '对话');
		expect(converseGroup).toBeDefined();
		expect(converseGroup!.items.map((i) => i.href)).toEqual([
			'/converse',
			'/interact',
			'/working-set'
		]);
	});

	it('T0b — 短期记忆 · 海马 group is filled by a statements deep-link (not empty)', () => {
		const hippocampusGroup = NAV_GROUPS.find((g) => g.title === '短期记忆 · 海马');
		expect(hippocampusGroup).toBeDefined();
		expect(hippocampusGroup!.items).toHaveLength(1);
		const item = hippocampusGroup!.items[0];
		expect(item.href).toBe(
			'/statements?consolidation_state=volatile,replaying_consolidating,replaying_reconsolidating'
		);
		expect(item.label).toBeTruthy();
		expect(item.icon).toBeTruthy();
	});

	it('T0d-1/T0d-2 — 长期记忆 · 新皮层 group has 全部/语义/规范 + 程序/画像/共识 六条', () => {
		const neocortexGroup = NAV_GROUPS.find((g) => g.title === '长期记忆 · 新皮层');
		expect(neocortexGroup).toBeDefined();
		expect(neocortexGroup!.items.map((i) => i.href)).toEqual([
			'/statements',
			'/statements?modality=believes,knows',
			'/statements?modality=norm_ought,norm_forbid',
			'/procedural',
			'/personae',
			'/common-ground'
		]);
		for (const item of neocortexGroup!.items) {
			expect(item.label).toBeTruthy();
			expect(item.icon).toBeTruthy();
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

// T0b+T0c fix — nav 深链高亮:matchesHref / activeNavItem 支持带 query 的 href。
describe('matchesHref — 深链 active 匹配', () => {
	const hippoHref =
		'/statements?consolidation_state=volatile,replaying_consolidating,replaying_reconsolidating';

	it('bare href matches当 pathname 相等(忽略 URL 上多余 query)', () => {
		expect(matchesHref('/statements', new URL('http://x/statements'))).toBe(true);
		expect(matchesHref('/statements', new URL('http://x/statements?foo=bar'))).toBe(true);
	});

	it('bare href 不匹配 pathname 不同', () => {
		expect(matchesHref('/statements', new URL('http://x/cognizers'))).toBe(false);
	});

	it('深链 href 仅在 query 参数命中时匹配', () => {
		expect(matchesHref(hippoHref, new URL('http://x' + hippoHref))).toBe(true);
	});

	it('深链 href 不匹配裸 /statements(query 缺失)', () => {
		expect(matchesHref(hippoHref, new URL('http://x/statements'))).toBe(false);
	});

	it('深链 href 不匹配不同 query 值', () => {
		expect(
			matchesHref(hippoHref, new URL('http://x/statements?consolidation_state=consolidated'))
		).toBe(false);
	});

	it('pathname 不同则 query 再全也不匹配', () => {
		expect(
			matchesHref(
				'/statements?consolidation_state=volatile',
				new URL('http://x/lens?consolidation_state=volatile')
			)
		).toBe(false);
	});
});

describe('activeNavItem — 面包屑/高亮选取', () => {
	it('裸 /statements URL → 匹配到长期记忆组的 /statements(无 query 项)', () => {
		const item = activeNavItem(new URL('http://x/statements'));
		expect(item?.href).toBe('/statements');
	});

	it('海马深链 URL → 优先匹配带 query 的深链项(而非裸 /statements)', () => {
		const url = new URL(
			'http://x/statements?consolidation_state=volatile,replaying_consolidating,replaying_reconsolidating'
		);
		const item = activeNavItem(url);
		expect(item?.href).toContain('consolidation_state=');
		expect(item?.group).toBe('短期记忆 · 海马');
	});

	it('无匹配 pathname → undefined', () => {
		expect(activeNavItem(new URL('http://x/nonexistent'))).toBeUndefined();
	});
});
