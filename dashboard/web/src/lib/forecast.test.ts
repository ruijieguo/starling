import { describe, it, expect } from 'vitest';
import { retrievabilityPct, riskTone, riskLabel } from './forecast';

describe('forecast helpers (Phase 3 片 5)', () => {
	it('retrievabilityPct: rounds + clamps to 0..100', () => {
		expect(retrievabilityPct(0.5)).toBe(50);
		expect(retrievabilityPct(0.367)).toBe(37);
		expect(retrievabilityPct(1.5)).toBe(100); // clamp high
		expect(retrievabilityPct(-0.2)).toBe(0); // clamp low
	});

	it('riskTone: thresholds 0.05 / 0.2 / 0.5 (0.05 aligned to op_decay archive)', () => {
		expect(riskTone(0.04)).toBe('danger');
		expect(riskTone(0.05)).toBe('warn'); // 0.05 is not < 0.05
		expect(riskTone(0.19)).toBe('warn');
		expect(riskTone(0.2)).toBe('info');
		expect(riskTone(0.49)).toBe('info');
		expect(riskTone(0.5)).toBe('success');
		expect(riskTone(0.9)).toBe('success');
	});

	it('riskLabel: matches the tone bands', () => {
		expect(riskLabel(0.04)).toBe('濒临归档');
		expect(riskLabel(0.1)).toBe('高危');
		expect(riskLabel(0.3)).toBe('衰减中');
		expect(riskLabel(0.8)).toBe('稳固');
	});
});
