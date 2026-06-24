import { describe, it, expect } from 'vitest';
import { modeLabel, opsSummary, hasSleepOrIdle } from './dream';

describe('dream log helpers (Phase 3 片 2)', () => {
	it('maps modes to label + tone, unknown falls back', () => {
		expect(modeLabel('online')).toEqual({ label: '在线', tone: 'neutral' });
		expect(modeLabel('idle').label).toBe('空闲');
		expect(modeLabel('sleep').tone).toBe('brand');
		expect(modeLabel('weird')).toEqual({ label: 'weird', tone: 'neutral' });
	});

	it('summarizes ops: known + unknown + zero-filtered + empty + bad json', () => {
		expect(opsSummary('{"op_compress":3,"op_archive":1}')).toBe('固化 3 · 归档 1');
		expect(opsSummary('{"op_compress":0}')).toBe('无操作'); // zero counts filtered out
		expect(opsSummary('{}')).toBe('无操作');
		expect(opsSummary('')).toBe('无操作');
		expect(opsSummary('{"mystery_op":2}')).toBe('mystery_op 2'); // unknown key kept raw
		expect(opsSummary('not json')).toBe('—');
	});

	it('detects sleep/idle presence (the not-wired-yet narrative gate)', () => {
		expect(hasSleepOrIdle([{ mode: 'online' }])).toBe(false);
		expect(hasSleepOrIdle([{ mode: 'online' }, { mode: 'sleep' }])).toBe(true);
		expect(hasSleepOrIdle([{ mode: 'idle' }])).toBe(true);
		expect(hasSleepOrIdle([])).toBe(false);
	});
});
