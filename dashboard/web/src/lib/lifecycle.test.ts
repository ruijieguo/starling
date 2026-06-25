import { describe, it, expect } from 'vitest';
import { occupancyStages, transitionFlows, consolidationDriven, stageLabel } from './lifecycle';

describe('lifecycle helpers (Phase 3 片 4)', () => {
	it('occupancyStages: orders stages, computes pct, zero total → pct 0', () => {
		const { total, stages } = occupancyStages({ volatile: 3, consolidated: 1 });
		expect(total).toBe(4);
		expect(stages.map((s) => s.key)).toEqual([
			'volatile',
			'replaying_consolidating',
			'consolidated',
			'archived',
			'forgotten'
		]);
		expect(stages[0].count).toBe(3);
		expect(stages[0].pct).toBe(75);
		expect(stages[2].pct).toBe(25);
		// 空库:total 0,pct 全 0(不除零)。
		expect(occupancyStages({}).stages.every((s) => s.pct === 0)).toBe(true);
	});

	it('transitionFlows: events drive most rows; 遗忘 from snapshot occupancy', () => {
		const flows = transitionFlows(
			{ 'statement.written': 5, 'statement.consolidated': 2, 'statement.archived': 1 },
			{ forgotten: 4 }
		);
		const by = Object.fromEntries(flows.map((f) => [f.key, f]));
		expect(by.written.count).toBe(5);
		expect(by.consolidated.count).toBe(2);
		expect(by.forgotten.count).toBe(4); // 快照派生
		expect(by.forgotten.source).toBe('snapshot');
		expect(by.written.source).toBe('event');
	});

	it('transitionFlows: consolidated folds in consolidation_forced', () => {
		const flows = transitionFlows(
			{ 'statement.consolidated': 2, 'statement.consolidation_forced': 3 },
			{}
		);
		expect(flows.find((f) => f.key === 'consolidated')!.count).toBe(5);
	});

	it('consolidationDriven: true only when a consolidated event exists', () => {
		expect(consolidationDriven({ 'statement.written': 9 })).toBe(false);
		expect(consolidationDriven({ 'statement.consolidated': 1 })).toBe(true);
		expect(consolidationDriven({ 'statement.consolidation_forced': 1 })).toBe(true);
	});

	it('stageLabel: maps known keys, unknown falls back to raw', () => {
		expect(stageLabel('consolidated')).toBe('长期 · 新皮层');
		expect(stageLabel('forgotten')).toBe('遗忘');
		expect(stageLabel('mystery')).toBe('mystery');
	});
});
