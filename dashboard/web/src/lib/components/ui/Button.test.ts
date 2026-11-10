import { describe, it, expect, vi } from 'vitest';
import { createRawSnippet } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import Button from './Button.svelte';

// 第 5 期 Task 5.1 修复轮（裁定 R110 I-1）：置灰按钮的 title 要能悬停出来。
// pointer-events: none 的元素不触发悬停提示，所以 disabled 时不能带 pointer-events-none；
// 改用 cursor-not-allowed，各 variant 的 hover 样式只在 enabled 时生效（免得置灰按钮悬停变色像能点）。
const label = createRawSnippet(() => ({ render: () => '<span>写入</span>' }));
const VARIANTS = ['primary', 'soft', 'secondary', 'ghost', 'danger'] as const;
const classes = (el: Element) => (el.getAttribute('class') ?? '').split(/\s+/).filter(Boolean);

describe('Button 置灰（裁定 R110 I-1）', () => {
	it('disabled 时保留悬停提示：没有 pointer-events-none，有 cursor-not-allowed，title 照常带上', () => {
		const { getByRole } = render(Button, {
			props: { disabled: true, title: '这个世界正被客户端写入：写入已置灰，召回可用', children: label }
		});
		const btn = getByRole('button') as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
		expect(classes(btn).some((c) => c.includes('pointer-events-none'))).toBe(false);
		expect(classes(btn)).toContain('disabled:cursor-not-allowed');
		expect(btn.getAttribute('title')).toBe('这个世界正被客户端写入：写入已置灰，召回可用');
	});

	it.each(VARIANTS)('variant %s：hover 样式都带 enabled: 前缀', (variant) => {
		const { getByRole } = render(Button, { props: { variant, disabled: true, children: label } });
		const hover = classes(getByRole('button')).filter((c) => c.includes('hover:'));
		expect(hover.length).toBeGreaterThan(0);
		expect(hover.filter((c) => !c.startsWith('enabled:hover:'))).toEqual([]);
	});

	// 「点击」按用户的点法模拟：btn.click()（HTMLElement.click，置灰的表单控件不激活）与点在按钮里的文字上
	// （Svelte 的事件委托对 disabled 的祖先不派发）。不用 fireEvent.click(btn)：它直接在置灰按钮上 dispatchEvent
	// 一个合成事件，浏览器里的用户点击不会这样派发，Svelte 的委托又对 event.target === 按钮本身放行，会误报。
	const userClicks = async (btn: HTMLElement) => {
		btn.click();
		await fireEvent.click(btn.querySelector('span')!);
	};

	it('disabled 时点击不触发 onclick（行为不随样式变化）；可用时触发', async () => {
		const onclick = vi.fn();
		const { getByRole, rerender } = render(Button, {
			props: { disabled: true, onclick, children: label }
		});
		await userClicks(getByRole('button'));
		expect(onclick).not.toHaveBeenCalled();
		await rerender({ disabled: false, onclick, children: label });
		await userClicks(getByRole('button'));
		expect(onclick).toHaveBeenCalledTimes(2);
	});

	it('loading 时同样置灰、不触发 onclick', async () => {
		const onclick = vi.fn();
		const { getByRole } = render(Button, { props: { loading: true, onclick, children: label } });
		expect((getByRole('button') as HTMLButtonElement).disabled).toBe(true);
		await userClicks(getByRole('button'));
		expect(onclick).not.toHaveBeenCalled();
	});
});
