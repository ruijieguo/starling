import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import DataTable from './DataTable.svelte';

const rows = [
	{ a: 'beta', b: 2 },
	{ a: 'alpha', b: 1 }
];

describe('DataTable', () => {
	it('shows EmptyState when no rows', () => {
		const { getByText } = render(DataTable, { props: { rows: [], columns: ['a'], emptyText: '空空如也' } });
		expect(getByText('空空如也')).toBeTruthy();
	});
	it('renders headers and rows', () => {
		const { getByText } = render(DataTable, { props: { rows, columns: ['a', 'b'] } });
		expect(getByText('alpha')).toBeTruthy();
		expect(getByText('beta')).toBeTruthy();
	});
	it('shows skeleton when loading', () => {
		const { container } = render(DataTable, { props: { rows: [], columns: ['a'], loading: true } });
		expect(container.querySelector('.animate-pulse')).toBeTruthy();
	});
});
