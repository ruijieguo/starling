import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import { page } from '$app/state';
import { noteDefaultWorld, noteWorldStatus } from '$lib/world.svelte';

// 这页的外部依赖：GET /api/conflicts、/api/cascade_preview；POST /api/reconsolidate 与 /api/forget(走 dashboard_write)。
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

import Conflicts from './+page.svelte';

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
// 两侧都是 consolidated：抽屉里两侧各有「再固化」与「遗忘」，共四个写入按钮。
const CONFLICTS = {
	by_kind: { CONFLICTS_WITH: 1 },
	conflicts: [
		{ src_id: 'S1', dst_id: 'S2', edge_kind: 'CONFLICTS_WITH', weight: 0.9,
		  src_subject: 'Bob', src_predicate: 'owns', src_object: 'auth', src_state: 'consolidated',
		  dst_subject: 'Ann', dst_predicate: 'owns', dst_object: 'auth', dst_state: 'consolidated' }
	]
};

const writeButtons = () =>
	[...document.body.querySelectorAll('[role="dialog"] button')].filter((b) =>
		['再固化', '遗忘'].includes(b.textContent?.trim() ?? '')
	) as HTMLButtonElement[];

async function openDrawer(c: HTMLElement) {
	await fireEvent.click(c.querySelector('ul button')!);
	await settle();
}

// ── 第 5 期 Task 5.1 补充轮：其余写入入口置灰（spec §14，裁定 R109） ─────────────────
describe('/conflicts 再固化、遗忘随世界状态置灰', () => {
	beforeEach(() => {
		get.mockReset().mockImplementation(async (path: string) =>
			path.includes('cascade_preview') ? { affected_count: 0, affected: [], truncated: false } : CONFLICTS
		);
		post.mockReset().mockResolvedValue({});
		noteDefaultWorld('default');
		(page as { url: URL }).url = new URL('http://localhost/conflicts?world=w1');
		noteWorldStatus('w1', null);
	});

	it.each([
		['被占用', { held_by_client: true }, HELD],
		['只读', { reclaimable: true, open_mode: 'ro' }, READ_ONLY]
	])('%s：两侧的「再固化」「遗忘」都 disabled 带 title，点了不发请求', async (_n, over, reason) => {
		noteWorldStatus('w1', { ...FLAGS, ...over } as typeof FLAGS);
		const { container } = render(Conflicts);
		await settle();
		await openDrawer(container);
		const btns = writeButtons();
		expect(btns.map((b) => b.textContent?.trim())).toEqual(['再固化', '遗忘', '再固化', '遗忘']);
		for (const b of btns) {
			expect(b.disabled).toBe(true);
			expect(b.getAttribute('title')).toBe(reason);
			await fireEvent.click(b);
		}
		await settle();
		expect(post).not.toHaveBeenCalled();
	});

	it('可写：四个按钮都可点、不带 title，「再固化」发 reconsolidate', async () => {
		noteWorldStatus('w1', FLAGS);
		const { container } = render(Conflicts);
		await settle();
		await openDrawer(container);
		for (const b of writeButtons()) {
			expect(b.disabled).toBe(false);
			expect(b.hasAttribute('title')).toBe(false);
		}
		await fireEvent.click(writeButtons()[0]);
		await settle();
		expect(post.mock.calls[0][0]).toBe('/api/w/w1/reconsolidate');
	});
});
