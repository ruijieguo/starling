import { describe, expect, it } from 'vitest';
import { stateTone, isHealthy, nonZeroMetrics, type RuntimeHealthResponse, type MetricsSnapshot } from './runtime_health';

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

const zeroMetrics: MetricsSnapshot = {
	outbox_lag_sequence: 0,
	subscriber_failure_rate: 0,
	extraction_queue_depth: 0,
	projection_lag_seconds: 0,
	runtime_event_loop_lag_ms: 0,
	vector_delete_lag: 0,
	erased_evidence_visible_count: 0
};

describe('nonZeroMetrics', () => {
	it('returns empty array when all metrics are zero', () => {
		expect(nonZeroMetrics(zeroMetrics)).toEqual([]);
	});
	it('returns only the non-zero metric when outbox_lag_sequence = 42', () => {
		const ms: MetricsSnapshot = { ...zeroMetrics, outbox_lag_sequence: 42 };
		const result = nonZeroMetrics(ms);
		expect(result).toContainEqual(['outbox_lag_sequence', 42]);
		// zero fields are excluded
		expect(result.every(([, v]) => v !== 0)).toBe(true);
	});
	it('returns both when outbox_lag_sequence = 5 and runtime_event_loop_lag_ms = 120', () => {
		const ms: MetricsSnapshot = { ...zeroMetrics, outbox_lag_sequence: 5, runtime_event_loop_lag_ms: 120 };
		const keys = nonZeroMetrics(ms).map(([k]) => k);
		expect(keys).toContain('outbox_lag_sequence');
		expect(keys).toContain('runtime_event_loop_lag_ms');
		expect(keys.length).toBe(2);
	});
	it('value 42 appears in result when outbox_lag_sequence = 42 (renders that value)', () => {
		const ms: MetricsSnapshot = { ...zeroMetrics, outbox_lag_sequence: 42 };
		const values = nonZeroMetrics(ms).map(([, v]) => v);
		expect(values).toContain(42);
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
