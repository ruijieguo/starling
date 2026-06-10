import { describe, expect, it } from 'vitest';
import { byDeadline, deriveFired, isOverdue } from './commitments';

describe('commitments utils', () => {
	it('deriveFired keeps only fired triggers', () => {
		const s = deriveFired([
			{ commitment_stmt_id: 'a', status: 'fired' },
			{ commitment_stmt_id: 'b', status: 'armed' },
			{ commitment_stmt_id: 'c', status: 'cleared' }
		]);
		expect(s.has('a')).toBe(true);
		expect(s.has('b')).toBe(false);
		expect(s.size).toBe(1);
	});

	it('deriveFired tolerates undefined', () => {
		expect(deriveFired(undefined).size).toBe(0);
	});

	it('byDeadline sorts ascending with missing deadlines last', () => {
		const rows = [
			{ id: 'late', deadline: '2026-06-20T00:00:00Z' },
			{ id: 'none', deadline: null },
			{ id: 'soon', deadline: '2026-06-11T00:00:00Z' }
		];
		expect([...rows].sort(byDeadline).map((r) => r.id)).toEqual(['soon', 'late', 'none']);
	});

	it('isOverdue compares against the provided now', () => {
		const now = '2026-06-10T12:00:00Z';
		expect(isOverdue('2026-06-09T00:00:00Z', now)).toBe(true);
		expect(isOverdue('2026-06-11T00:00:00Z', now)).toBe(false);
		expect(isOverdue(null, now)).toBe(false);
	});
});
