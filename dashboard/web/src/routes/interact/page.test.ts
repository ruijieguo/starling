import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import { page } from '$app/state';
import { noteDefaultWorld, noteWorldStatus } from '$lib/world.svelte';

// 这页的外部依赖：GET /api/config(模型下拉)、POST /api/remember 与 /api/recall。
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

import Interact from './+page.svelte';
import { WRITABLE_FLAGS, flagsWith } from '$lib/test/world-status';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

const HELD = '这个世界正被客户端写入：写入已置灰，召回可用';
const READ_ONLY = '只读世界（种子或复盘副本）：可以检视和召回，不能写入';

const byText = (t: string) =>
	[...document.body.querySelectorAll('button')].find((b) => b.textContent?.trim() === t) as
		| HTMLButtonElement
		| undefined;

// ── 第 5 期 Task 5.1：写入类按钮置灰（spec §14，裁定 R108） ─────────────────────
describe('/interact「记住」随世界状态置灰，召回照常', () => {
	beforeEach(() => {
		get.mockReset().mockResolvedValue({ providers: {} });
		post.mockReset().mockResolvedValue({ results: [] });
		noteDefaultWorld('default');
		(page as { url: URL }).url = new URL('http://localhost/interact?world=w1');
		noteWorldStatus('w1', null);
	});

	const typeBoth = async (c: HTMLElement) => {
		await fireEvent.input(c.querySelector('textarea')!, { target: { value: 'Bob owns auth' } });
		await fireEvent.input(c.querySelector('input[placeholder="query"]')!, {
			target: { value: 'auth' }
		});
		await tick();
	};

	it.each([
		['被占用', { held_by_client: true }, HELD],
		['只读', { reclaimable: true, open_mode: 'ro' }, READ_ONLY]
	])('%s：「记住」disabled 带 title，点了不发 remember；「检索」可用', async (_n, over, reason) => {
		noteWorldStatus('w1', flagsWith(over));
		const { container } = render(Interact);
		await settle();
		await typeBoth(container);
		const remember = byText('记住')!;
		expect(remember.disabled).toBe(true);
		expect(remember.getAttribute('title')).toBe(reason);
		await fireEvent.click(remember);
		await settle();
		expect(post).not.toHaveBeenCalled();
		const recall = byText('检索')!;
		expect(recall.disabled).toBe(false);
		await fireEvent.click(recall);
		await settle();
		expect(post).toHaveBeenCalledTimes(1);
		expect(post.mock.calls[0][0]).toBe('/api/w/w1/recall');
	});

	it('可写：「记住」可点、不带 title', async () => {
		noteWorldStatus('w1', WRITABLE_FLAGS);
		const { container } = render(Interact);
		await settle();
		await typeBoth(container);
		expect(byText('记住')!.disabled).toBe(false);
		expect(byText('记住')!.hasAttribute('title')).toBe(false);
	});
});
