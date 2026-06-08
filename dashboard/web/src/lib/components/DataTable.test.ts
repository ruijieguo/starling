import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
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
	it('sorts numeric columns naturally (10 after 2), not lexicographically', async () => {
		const { getByRole, container } = render(DataTable, {
			props: { rows: [{ n: 2 }, { n: 10 }, { n: 1 }], columns: ['n'], filterable: false }
		});
		await fireEvent.click(getByRole('button')); // ascending sort on the only column
		const cells = [...container.querySelectorAll('tbody td')].map((td) => td.textContent);
		expect(cells).toEqual(['1', '2', '10']);
	});
	it('shows "无匹配结果" when the filter excludes every row', async () => {
		const { getByPlaceholderText, getByText } = render(DataTable, {
			props: { rows: [{ a: 'alpha' }], columns: ['a'] }
		});
		await fireEvent.input(getByPlaceholderText('筛选…'), { target: { value: 'zzz' } });
		expect(getByText('无匹配结果')).toBeTruthy();
	});
});
