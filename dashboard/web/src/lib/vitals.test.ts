import { describe, expect, it } from 'vitest';
import { allHealthy, lagTone, type VitalsResponse } from './vitals';

describe('lagTone', () => {
	it('null lag → unknown (checkpoint table absent, not fake-green)', () => {
		expect(lagTone(null)).toEqual({ tone: 'unknown', label: '无 checkpoint' });
	});
	it('0 → healthy', () => {
		expect(lagTone(0)).toEqual({ tone: 'success', label: '健康' });
	});
	it('within threshold → warn', () => {
		expect(lagTone(5).tone).toBe('warn');
		expect(lagTone(20).tone).toBe('warn');
	});
	it('over threshold → danger', () => {
		expect(lagTone(21).tone).toBe('danger');
		expect(lagTone(999).tone).toBe('danger');
	});
});

describe('allHealthy', () => {
	const base: VitalsResponse = {
		outbox_head: 10,
		max_lag: 0,
		lag: [],
		volatile_stuck: [],
		volatile_stuck_total: 0,
		extraction_failures: [],
		extraction_failures_total: 0,
		extraction_cost: {
			attempts: 0,
			prompt_tokens: 0,
			completion_tokens: 0,
			total_tokens: 0,
			latency_ms: 0
		},
		extraction_cost_runs: [],
		overdue_windows: [],
		overdue_windows_total: 0
	};
	it('all-zero → healthy', () => {
		expect(allHealthy(base)).toBe(true);
	});
	it('any lag → not healthy', () => {
		expect(allHealthy({ ...base, max_lag: 3 })).toBe(false);
	});
	it('stuck/failed/overdue → not healthy', () => {
		expect(allHealthy({ ...base, volatile_stuck_total: 1 })).toBe(false);
		expect(allHealthy({ ...base, extraction_failures_total: 1 })).toBe(false);
		expect(allHealthy({ ...base, overdue_windows_total: 1 })).toBe(false);
	});
});
