import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import StatCard from './StatCard.svelte';

describe('StatCard', () => {
	it('renders label and value', () => {
		const { getByText } = render(StatCard, { props: { label: 'statements', value: 42 } });
		expect(getByText('statements')).toBeTruthy();
		expect(getByText('42')).toBeTruthy();
	});
	it('shows up arrow for positive trend', () => {
		const { getByText } = render(StatCard, { props: { label: 'x', value: 1, trend: 2 } });
		expect(getByText('↑2')).toBeTruthy();
	});
});
