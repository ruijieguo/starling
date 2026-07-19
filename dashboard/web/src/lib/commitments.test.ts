import { describe, expect, it } from 'vitest';
import {
	byDeadline,
	deriveFired,
	describeTrigger,
	isOverdue,
	triggerKindLabel,
	triggersFor
} from './commitments';

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

	// T0f — trigger 四型分型呈现
	it('triggerKindLabel maps four kinds + falls back', () => {
		expect(triggerKindLabel('time')).toBe('定时');
		expect(triggerKindLabel('event')).toBe('事件');
		expect(triggerKindLabel('state')).toBe('状态');
		expect(triggerKindLabel('compound')).toBe('复合');
		expect(triggerKindLabel('mystery')).toBe('mystery'); // 未知回退原值
		expect(triggerKindLabel(undefined)).toBe('未知');
	});

	it('triggersFor filters to one commitment', () => {
		const all = [
			{ commitment_stmt_id: 'a', kind: 'time', status: 'armed' },
			{ commitment_stmt_id: 'b', kind: 'event', status: 'armed' },
			{ commitment_stmt_id: 'a', kind: 'state', status: 'fired' }
		];
		expect(triggersFor(all, 'a').map((t) => t.kind)).toEqual(['time', 'state']);
		expect(triggersFor(all, 'b')).toHaveLength(1);
		expect(triggersFor(all, 'z')).toHaveLength(0);
		expect(triggersFor(undefined, 'a')).toHaveLength(0);
	});

	it('describeTrigger summarizes each of the four types from spec_json', () => {
		expect(
			describeTrigger({
				commitment_stmt_id: 'x',
				kind: 'time',
				status: 'armed',
				spec_json: JSON.stringify({ fire_at: '2026-07-01T00:00:00Z' })
			})
		).toContain('2026-07-01T00:00:00Z');
		expect(
			describeTrigger({
				commitment_stmt_id: 'x',
				kind: 'event',
				status: 'armed',
				spec_json: JSON.stringify({ event_type: 'statement.written' })
			})
		).toContain('statement.written');
		expect(
			describeTrigger({
				commitment_stmt_id: 'x',
				kind: 'state',
				status: 'armed',
				spec_json: JSON.stringify({ field: 'consolidation_state' })
			})
		).toContain('consolidation_state');
		expect(
			describeTrigger({
				commitment_stmt_id: 'x',
				kind: 'compound',
				status: 'armed',
				spec_json: JSON.stringify({ mode: 'all_of', children: [1, 2, 3] })
			})
		).toContain('3');
	});

	it('describeTrigger degrades gracefully on malformed / missing spec_json', () => {
		expect(
			describeTrigger({ commitment_stmt_id: 'x', kind: 'time', status: 'armed', spec_json: '{bad' })
		).toBe('(规格无法解析)');
		// 缺字段 → 回退到该型的通用文案,不崩
		expect(
			describeTrigger({ commitment_stmt_id: 'x', kind: 'event', status: 'armed', spec_json: '{}' })
		).toBe('事件触发');
		// 无 spec_json + 未知 kind → 通用兜底
		expect(describeTrigger({ commitment_stmt_id: 'x', status: 'armed' })).toBe('触发');
	});
});
