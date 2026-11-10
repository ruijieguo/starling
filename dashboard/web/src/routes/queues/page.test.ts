import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';

// 这页的外部依赖：GET /api/queues(加载)与 POST /api/tick(手动 tick)。
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
const toastSuccess = vi.fn();
const toastWarning = vi.fn();
vi.mock('$lib/ui/toast', () => ({
	toast: {
		error: (...a: unknown[]) => toastError(...a),
		success: (...a: unknown[]) => toastSuccess(...a),
		warning: (...a: unknown[]) => toastWarning(...a),
		info: vi.fn()
	}
}));

import Queues from './+page.svelte';
import { WRITABLE_FLAGS, flagsWith } from '$lib/test/world-status';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

const QUEUES = { dispatch: { pending: 0 }, embedding_backlog: 3, vectors_by_status: { embedded: 1 } };
const TICK_BASE = { embedded: 0, fired: 0, stage_timings_ms: {}, stages_skipped: [] as string[] };

const tickButton = () =>
	[...document.body.querySelectorAll('button')].find((b) => b.textContent?.trim() === '手动 Tick') as
		| HTMLButtonElement
		| undefined;

describe('/queues 手动 tick（裁定 R59 N-4）', () => {
	beforeEach(() => {
		get.mockReset().mockResolvedValue(QUEUES);
		post.mockReset();
		toastError.mockReset();
		toastSuccess.mockReset();
		toastWarning.mockReset();
	});

	it('stages_skipped 含 embed：成功之外 toast.warning 指向重新确认端点', async () => {
		post.mockResolvedValue({ ...TICK_BASE, stages_skipped: ['embed'] });
		render(Queues);
		await settle();
		await fireEvent.click(tickButton()!);
		await settle();
		expect(toastSuccess).toHaveBeenCalledWith('Tick 发送成功');
		expect(toastWarning).toHaveBeenCalledWith(
			'嵌入端点失效，本轮跳过嵌入；到「世界」页重新确认端点'
		);
	});

	it('没跳过嵌入：不出 warning', async () => {
		post.mockResolvedValue({ ...TICK_BASE, stages_skipped: ['persona'] });
		render(Queues);
		await settle();
		await fireEvent.click(tickButton()!);
		await settle();
		expect(toastSuccess).toHaveBeenCalledWith('Tick 发送成功');
		expect(toastWarning).not.toHaveBeenCalled();
	});
});

// ── 第 5 期 Task 5.1：写入类按钮置灰（spec §14，裁定 R108） ─────────────────────
describe('/queues 手动 Tick 随世界状态置灰', () => {
	beforeEach(async () => {
		const { noteDefaultWorld, noteWorldStatus } = await import('$lib/world.svelte');
		const { page } = await import('$app/state');
		(page as { url: URL }).url = new URL('http://localhost/queues');
		noteDefaultWorld('default');
		noteWorldStatus('default', null);
		get.mockReset().mockResolvedValue(QUEUES);
		post.mockReset();
	});

	it('被客户端占着：disabled，title 是横幅的占用文案；点了也不发 tick', async () => {
		const { noteWorldStatus } = await import('$lib/world.svelte');
		noteWorldStatus('default', flagsWith({ held_by_client: true }));
		render(Queues);
		await settle();
		const btn = tickButton()!;
		expect(btn.disabled).toBe(true);
		expect(btn.getAttribute('title')).toBe('这个世界正被客户端写入：写入已置灰，召回可用');
		await fireEvent.click(btn);
		await settle();
		expect(post).not.toHaveBeenCalled();
	});

	it('只读世界：disabled，title 是只读文案', async () => {
		const { noteWorldStatus } = await import('$lib/world.svelte');
		noteWorldStatus('default', flagsWith({ reclaimable: true, open_mode: 'ro' }));
		render(Queues);
		await settle();
		expect(tickButton()!.disabled).toBe(true);
		expect(tickButton()!.getAttribute('title')).toBe(
			'只读世界（种子或复盘副本）：可以检视和召回，不能写入'
		);
	});

	it('可写、状态未知、或状态属于别的世界：照常可点，不带 title', async () => {
		const { noteWorldStatus } = await import('$lib/world.svelte');
		render(Queues);
		await settle();
		expect(tickButton()!.disabled).toBe(false);
		expect(tickButton()!.hasAttribute('title')).toBe(false);
		noteWorldStatus('other', flagsWith({ held_by_client: true }));
		await settle();
		expect(tickButton()!.disabled).toBe(false);
		noteWorldStatus('default', flagsWith({ schema_behind: true }));   // schema 落后不挡写入
		await settle();
		expect(tickButton()!.disabled).toBe(false);
	});
});
