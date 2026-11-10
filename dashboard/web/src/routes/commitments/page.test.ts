import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import { page } from '$app/state';
import { noteDefaultWorld, noteWorldStatus } from '$lib/world.svelte';

// 这页的外部依赖：GET /api/commitments；POST /api/commitment/fulfill|withdraw(走 dashboard_write)。
const get = vi.fn();
const post = vi.fn();
vi.mock('$lib/api', async (orig) => {
	const real = await orig<typeof import('$lib/api')>();
	return {
		...real,
		api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), del: vi.fn() }
	};
});
vi.mock('$lib/ui/toast', () => ({
	toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() }
}));

import Commitments from './+page.svelte';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

const FLAGS = {
	seed: false, read_only: false, reclaimable: false, open_mode: 'rw' as const,
	schema_behind: false, held_by_client: false
};
const HELD = '这个世界正被客户端写入：写入已置灰，召回可用';
const READ_ONLY = '只读世界（种子或复盘副本）：可以检视和召回，不能写入';
const DATA = {
	rows: [
		{ stmt_id: 'C1', state: 'ACTIVE', subject_id: 'self', predicate: 'promises', object_value: 'ship',
		  broken_count: 0, deadline: null, created_at: '', updated_at: '' }
	],
	triggers: []
};

const byText = (t: string) =>
	[...document.body.querySelectorAll('[role="dialog"] button')].find(
		(b) => b.textContent?.trim() === t
	) as HTMLButtonElement | undefined;

async function openDrawer(c: HTMLElement) {
	const card = [...c.querySelectorAll('ul button')].find((b) => b.textContent?.includes('promises'))!;
	await fireEvent.click(card);
	await settle();
}

// ── 第 5 期 Task 5.1 补充轮：其余写入入口置灰（spec §14，裁定 R109） ─────────────────
describe('/commitments 标记完成、撤回随世界状态置灰', () => {
	beforeEach(() => {
		get.mockReset().mockResolvedValue(DATA);
		post.mockReset().mockResolvedValue({});
		noteDefaultWorld('default');
		(page as { url: URL }).url = new URL('http://localhost/commitments?world=w1');
		noteWorldStatus('w1', null);
	});

	it.each([
		['被占用', { held_by_client: true }, HELD],
		['只读', { seed: true, read_only: true, open_mode: 'ro' }, READ_ONLY]
	])('%s：「标记完成」「撤回」disabled 带 title，点了不发请求', async (_n, over, reason) => {
		noteWorldStatus('w1', { ...FLAGS, ...over } as typeof FLAGS);
		const { container } = render(Commitments);
		await settle();
		await openDrawer(container);
		for (const t of ['标记完成', '撤回']) {
			const btn = byText(t)!;
			expect(btn.disabled, t).toBe(true);
			expect(btn.getAttribute('title'), t).toBe(reason);
			await fireEvent.click(btn);
		}
		await settle();
		expect(post).not.toHaveBeenCalled();
	});

	it('可写：两个按钮可点、不带 title，「标记完成」发 commitment/fulfill', async () => {
		noteWorldStatus('w1', FLAGS);
		const { container } = render(Commitments);
		await settle();
		await openDrawer(container);
		for (const t of ['标记完成', '撤回']) {
			expect(byText(t)!.disabled, t).toBe(false);
			expect(byText(t)!.hasAttribute('title'), t).toBe(false);
		}
		await fireEvent.click(byText('标记完成')!);
		await settle();
		expect(post.mock.calls[0][0]).toBe('/api/w/w1/commitment/fulfill');
	});
});
