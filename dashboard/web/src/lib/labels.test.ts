import { describe, it, expect } from 'vitest';
import { labelFor, glossFor, orderedEntries } from './labels';

describe('labels (T5 友好标签 + 策展呈现)', () => {
	it('labelFor: known keys map to Chinese friendly names', () => {
		expect(labelFor('statements')).toBe('语句');
		expect(labelFor('statement_edges')).toBe('关系边');
		expect(labelFor('cognizers')).toBe('认知体');
		expect(labelFor('commitments')).toBe('承诺');
		expect(labelFor('bus_events')).toBe('总线事件');
		expect(labelFor('ACTIVE')).toBe('生效中');
		expect(labelFor('pending')).toBe('待派发');
		expect(labelFor('embedded')).toBe('已嵌入');
		expect(labelFor('last_updated_at')).toBe('更新于');
	});

	it('labelFor: unknown key falls back to the raw key (never throws)', () => {
		expect(labelFor('some_new_backend_key')).toBe('some_new_backend_key');
		expect(labelFor('')).toBe('');
	});

	it('glossFor: returns gloss for entries that have one, undefined otherwise', () => {
		expect(glossFor('statements')).toBe('新皮层长期记忆的原子命题总数');
		expect(glossFor('ACTIVE')).toBeUndefined(); // no gloss defined
		expect(glossFor('unknown_key')).toBeUndefined();
	});

	it('orderedEntries: sorts known keys by curated weight regardless of input order', () => {
		const input = { bus_events: 4, statements: 1, cognizers: 2 };
		expect(orderedEntries(input).map(([k]) => k)).toEqual(['statements', 'cognizers', 'bus_events']);
	});

	it('orderedEntries: preserves values alongside sorted keys', () => {
		const input = { commitments: 7, statements: 3 };
		expect(orderedEntries(input)).toEqual([
			['statements', 3],
			['commitments', 7]
		]);
	});

	it('orderedEntries: unknown keys land after known keys, preserving relative order', () => {
		const input = { mystery_b: 2, statements: 1, mystery_a: 3, cognizers: 4 };
		expect(orderedEntries(input).map(([k]) => k)).toEqual([
			'statements',
			'cognizers',
			'mystery_b',
			'mystery_a'
		]);
	});

	it('orderedEntries: all-unknown object keeps input order, no crash', () => {
		const input = { foo: 1, bar: 2 };
		expect(orderedEntries(input)).toEqual([
			['foo', 1],
			['bar', 2]
		]);
	});

	it('orderedEntries: null/undefined input → empty array (defensive)', () => {
		expect(orderedEntries(null)).toEqual([]);
		expect(orderedEntries(undefined)).toEqual([]);
	});

	it('orderedEntries: empty object → empty array', () => {
		expect(orderedEntries({})).toEqual([]);
	});

	it('orderedEntries: commitment states sort in the six-state machine order', () => {
		const input = {
			WITHDRAWN: 1,
			created: 2,
			BROKEN: 3,
			ACTIVE: 4,
			FULFILLED: 5,
			RENEGOTIATED: 6
		};
		expect(orderedEntries(input).map(([k]) => k)).toEqual([
			'created',
			'ACTIVE',
			'FULFILLED',
			'BROKEN',
			'RENEGOTIATED',
			'WITHDRAWN'
		]);
	});
});
