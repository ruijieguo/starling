import { describe, expect, it } from 'vitest';
import { stateTone, isHealthy, type RuntimeHealthResponse } from './runtime_health';

describe('stateTone', () => {
	it('READY → success', () => {
		expect(stateTone('READY')).toBe('success');
	});
	it('DEGRADED → warn', () => {
		expect(stateTone('DEGRADED')).toBe('warn');
	});
	it('DRAINING → info (design-review D2: distinct from DEGRADED warn — intentional wind-down)', () => {
		expect(stateTone('DRAINING')).toBe('info');
	});
	it('UNREADY → danger', () => {
		expect(stateTone('UNREADY')).toBe('danger');
	});
	it('DRAINING must NOT collide with DEGRADED (D2)', () => {
		expect(stateTone('DRAINING')).not.toBe(stateTone('DEGRADED'));
	});
});

describe('isHealthy', () => {
	const base: RuntimeHealthResponse = {
		status: 'READY',
		events: []
	};
	it('READY → healthy', () => {
		expect(isHealthy(base)).toBe(true);
	});
	it('DEGRADED → not healthy', () => {
		expect(isHealthy({ ...base, status: 'DEGRADED' })).toBe(false);
	});
	it('DRAINING → not healthy', () => {
		expect(isHealthy({ ...base, status: 'DRAINING' })).toBe(false);
	});
	it('UNREADY → not healthy', () => {
		expect(isHealthy({ ...base, status: 'UNREADY' })).toBe(false);
	});
});
