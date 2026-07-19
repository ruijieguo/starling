import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import ScoreBreakdown from './ScoreBreakdown.svelte';

const row = {
	statement_id: 'stmt-0123456789',
	base: 0.8,
	recency: 0.5,
	salience: 0.6,
	activation: 0.4,
	affect_consistency: 0.9,
	temporal_penalty: 0.1,
	final_score: 0.712
};

describe('ScoreBreakdown', () => {
	it('renders all six factor labels', () => {
		const { getByText } = render(ScoreBreakdown, { props: { row } });
		expect(getByText('基础相关度')).toBeTruthy();
		expect(getByText('时近性')).toBeTruthy();
		expect(getByText('显著性')).toBeTruthy();
		expect(getByText('激活度')).toBeTruthy();
		expect(getByText('情感一致性')).toBeTruthy();
		expect(getByText('时效惩罚')).toBeTruthy();
	});

	it('renders the two-decimal value alongside each factor', () => {
		const { getByText } = render(ScoreBreakdown, { props: { row } });
		expect(getByText('0.80')).toBeTruthy();
		expect(getByText('0.50')).toBeTruthy();
		expect(getByText('0.10')).toBeTruthy();
	});

	it('handles an all-zero row without dividing by zero', () => {
		const zeroRow = { ...row, base: 0, recency: 0, salience: 0, activation: 0, affect_consistency: 0, temporal_penalty: 0 };
		const { container } = render(ScoreBreakdown, { props: { row: zeroRow } });
		// No segment has positive share, so the stacked bar renders no filled segments,
		// but the legend row (with 0.00 values) must still render without NaN/Infinity.
		expect(container.innerHTML).not.toContain('NaN');
		expect(container.innerHTML).not.toContain('Infinity');
	});
});
