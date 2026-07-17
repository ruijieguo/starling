import { describe, it, expect } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import DataTable from './DataTable.svelte';
import { density } from '../ui/density';

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
	it('fires onRowClick with the clicked row', async () => {
		let clicked: Record<string, unknown> | null = null;
		const { getByText } = render(DataTable, {
			props: { rows: [{ a: 'alpha' }], columns: ['a'], filterable: false, onRowClick: (r) => (clicked = r) }
		});
		await fireEvent.click(getByText('alpha'));
		expect(clicked).toEqual({ a: 'alpha' });
	});
	// 回归(T10 review Important#2): density 切换使每页行数增大、总页数缩小时,须回第 1 页,
	// 不可停在越界空页。真实场景=rows 引用不变、仅 density store 变化(用户点 header 密度切换),
	// 这正是旧实现漏的:回第1页的 $effect 只依赖 rows,不依赖 effectivePageSize。
	// 不传 pageSize prop → 走 pageSizeFor($density)(comfortable 12 / compact 25)。
	it('resets to page 1 when density change shrinks total pages (no out-of-bounds empty page)', async () => {
		density.set('comfortable'); // 12/页
		const many = Array.from({ length: 40 }, (_, i) => ({ n: i }));
		const { getByRole, container } = render(DataTable, {
			props: { rows: many, columns: ['n'], filterable: false } // 无 pageSize → 跟随 density
		});
		// 跳到最后一页(40 行 @12/页 = 4 页, page index 3)
		const nextBtn = getByRole('button', { name: '下一页' });
		await fireEvent.click(nextBtn);
		await fireEvent.click(nextBtn);
		await fireEvent.click(nextBtn);
		expect(container.textContent).toContain('第 4/4 页');
		// 切紧凑(25/页 → 只剩 2 页);rows 引用没变。旧实现 page 停在 3 → slice(75,100)=空。
		density.set('compact');
		await tick();
		const bodyCells = container.querySelectorAll('tbody td');
		expect(bodyCells.length).toBeGreaterThan(0); // 修复后回第1页有行;bug 时 tbody 为空
		expect(bodyCells[0].textContent).toBe('0'); // 回到首行
		expect(container.textContent).not.toContain('第 4/'); // 不再停在越界的第 4 页
	});
});
