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
const toastError = vi.fn();
vi.mock('$lib/ui/toast', () => ({
	toast: { error: (...a: unknown[]) => toastError(...a), success: vi.fn(), warning: vi.fn(), info: vi.fn() }
}));

import Commitments from './+page.svelte';
import { ApiError } from '$lib/api';
import { WRITABLE_FLAGS, flagsWith } from '$lib/test/world-status';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
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

// 抽屉(bits-ui Dialog)打开时,DismissibleLayer 用 afterSleep(1) 排一个 1 ms 的定时器,到点读抽屉内容的 ref。
// 测试里打开、点击、卸载都在微任务里完成,定时器要等整个文件跑完才轮到,那时抽屉早已销毁,Svelte 打出
// derived_inert(裁定 R113 M4;调用栈指向 use-dismissable-layer.svelte.js 的 afterSleep)。真实用户点不了这么快,
// 所以打开后让出一次宏任务,让定时器在抽屉还在时跑完。
const macrotask = () => new Promise<void>((r) => setTimeout(r, 5));

async function openDrawer(c: HTMLElement) {
	const card = [...c.querySelectorAll('ul button')].find((b) => b.textContent?.includes('promises'))!;
	await fireEvent.click(card);
	await settle();
	await macrotask();
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
		noteWorldStatus('w1', flagsWith(over));
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
		noteWorldStatus('w1', WRITABLE_FLAGS);
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
		// 等异步收尾再结束(裁定 R113 M4):成功后重取看板、关抽屉。
		await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
		await vi.waitFor(() => expect(byText('标记完成'), '抽屉应已关').toBeUndefined());
	});
});

// ── 裁定 R113 I-1：后端拒绝时按 detail 区分，只有 not_active 才是「已非 ACTIVE」 ─────────────────
describe('/commitments 流转被 409 拒绝', () => {
	beforeEach(() => {
		get.mockReset().mockResolvedValue(DATA);
		post.mockReset();
		toastError.mockReset();
		noteDefaultWorld('default');
		(page as { url: URL }).url = new URL('http://localhost/commitments?world=w1');
		noteWorldStatus('w1', WRITABLE_FLAGS);
	});

	const fulfill = async () => {
		const { container } = render(Commitments);
		await settle();
		await openDrawer(container);
		await fireEvent.click(byText('标记完成')!);
		await settle();
	};

	it('409 world_held：提示占用(横幅那句)，不说「已非 ACTIVE」，抽屉不关、不重取', async () => {
		post.mockRejectedValue(new ApiError(409, '/api/w/w1/commitment/fulfill', '409 world_held'));
		await fulfill();
		expect(toastError).toHaveBeenCalledTimes(1);
		expect(toastError).toHaveBeenCalledWith('流转失败:这个世界正被客户端写入：写入已置灰，召回可用');
		expect(byText('标记完成'), '抽屉应仍开着').toBeDefined();
		expect(get).toHaveBeenCalledTimes(1);
	});

	it('409 not_active：维持原行为——提示已非 ACTIVE、关抽屉、重取', async () => {
		post.mockRejectedValue(new ApiError(409, '/api/w/w1/commitment/fulfill', '409 not_active'));
		await fulfill();
		expect(toastError).toHaveBeenCalledWith(
			'无法流转:该承诺已非 ACTIVE 或不存在(可能已被后台 tick 改变);已刷新'
		);
		await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
		await settle();
		expect(byText('标记完成'), '抽屉应已关').toBeUndefined();
	});
});
