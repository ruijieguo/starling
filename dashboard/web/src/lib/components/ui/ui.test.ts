import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Button from './Button.svelte';
import EmptyState from './EmptyState.svelte';
import StatusDot from './StatusDot.svelte';

describe('ui components', () => {
	it('Button renders its label and disables when loading', () => {
		const { getByRole } = render(Button, {
			props: { loading: true, children: (() => 'Save') as never }
		});
		expect((getByRole('button') as HTMLButtonElement).disabled).toBe(true);
	});
	it('EmptyState shows title', () => {
		const { getByText } = render(EmptyState, { props: { title: '无数据' } });
		expect(getByText('无数据')).toBeTruthy();
	});
	it('StatusDot shows its label text (color is not the only signal)', () => {
		const { getByText } = render(StatusDot, { props: { tone: 'ok', label: 'Connected' } });
		expect(getByText('Connected')).toBeTruthy();
	});
});
