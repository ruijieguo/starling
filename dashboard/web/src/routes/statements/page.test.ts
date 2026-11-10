import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import { page } from '$app/state';
import { noteDefaultWorld, noteWorldStatus } from '$lib/world.svelte';

const get = vi.fn();
const post = vi.fn();
vi.mock('$lib/api', async (orig) => {
	const real = await orig<typeof import('$lib/api')>();
	return { ...real, api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } };
});
vi.mock('$lib/ui/toast', () => ({
	toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() }
}));

import Statements from './+page.svelte';
import { WRITABLE_FLAGS, flagsWith } from '$lib/test/world-status';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};
const at = (u: string) => {
	(page as { url: URL }).url = new URL(u, 'http://localhost');
};
const rowsOf = (tag: string) => ({
	rows: [
		{ id: 'S1', subject_id: tag, predicate: 'likes', object_value: 'tea', holder_id: 'h',
		  consolidation_state: 'volatile', review_status: 'ok', observed_at: '' }
	]
});

describe('/statements 详情抽屉与换世界', () => {
	beforeEach(() => {
		get.mockReset().mockImplementation(async (path: string) =>
			rowsOf(path.startsWith('/api/w/') ? 'subj-w1' : 'subj-default')
		);
		noteDefaultWorld('default');
		at('/statements');
	});

	it('抽屉开着时换世界：抽屉关闭，旧世界的行不再挂在新世界下；列表按新世界路径重取', async () => {
		const { container } = render(Statements);
		await settle();
		await fireEvent.click(container.querySelector('tbody tr')!);
		await settle();
		expect(document.body.textContent).toContain('Statement 详情');
		const dlg = () => document.body.querySelector('[role="dialog"]');
		expect(dlg()?.textContent).toContain('subj-default');

		at('/statements?world=w1');
		await settle();
		expect(dlg()?.textContent ?? '').not.toContain('subj-default');
		expect(get.mock.calls.some((c) => String(c[0]).startsWith('/api/w/w1/statements'))).toBe(true);
	});
});

// ── 第 5 期 Task 5.1 补充轮：其余写入入口置灰（spec §14，裁定 R109） ─────────────────
describe('/statements 批准、拒绝、再固化、遗忘随世界状态置灰', () => {
	const HELD = '这个世界正被客户端写入：写入已置灰，召回可用';
	const READ_ONLY = '只读世界（种子或复盘副本）：可以检视和召回，不能写入';
	const WRITES = ['批准', '拒绝', '请求再固化', '遗忘'];
	// 待复核且已固化：抽屉里四个写入按钮都出现。
	const ROWS = {
		rows: [
			{ id: 'S1', subject_id: 'Bob', predicate: 'owns', object_value: 'auth', holder_id: 'h',
			  consolidation_state: 'consolidated', review_status: 'review_requested', observed_at: '' }
		]
	};
	const inDrawer = (t: string) =>
		[...document.body.querySelectorAll('[role="dialog"] button')].find(
			(b) => b.textContent?.trim() === t
		) as HTMLButtonElement | undefined;
	async function openDrawer(c: HTMLElement) {
		await fireEvent.click(c.querySelector('tbody tr')!);
		await settle();
	}

	beforeEach(() => {
		get.mockReset().mockResolvedValue(ROWS);
		post.mockReset().mockResolvedValue({});
		noteDefaultWorld('default');
		at('/statements?world=w1');
		noteWorldStatus('w1', null);
	});

	it.each([
		['被占用', { held_by_client: true }, HELD],
		['只读', { reclaimable: true, open_mode: 'ro' }, READ_ONLY]
	])('%s：四个写入按钮 disabled 带 title，点了不发请求；「透视来源」照常', async (_n, over, reason) => {
		noteWorldStatus('w1', flagsWith(over));
		const { container } = render(Statements);
		await settle();
		await openDrawer(container);
		for (const t of WRITES) {
			const btn = inDrawer(t)!;
			expect(btn, t).toBeTruthy();
			expect(btn.disabled, t).toBe(true);
			expect(btn.getAttribute('title'), t).toBe(reason);
			await fireEvent.click(btn);
		}
		await settle();
		expect(post).not.toHaveBeenCalled();
		expect(inDrawer('透视来源 →')!.disabled).toBe(false);
	});

	it('可写：四个按钮都可点、不带 title，「批准」发 review', async () => {
		noteWorldStatus('w1', WRITABLE_FLAGS);
		const { container } = render(Statements);
		await settle();
		await openDrawer(container);
		for (const t of WRITES) {
			expect(inDrawer(t)!.disabled, t).toBe(false);
			expect(inDrawer(t)!.hasAttribute('title'), t).toBe(false);
		}
		await fireEvent.click(inDrawer('批准')!);
		await settle();
		expect(post.mock.calls[0][0]).toBe('/api/w/w1/review');
	});
});
