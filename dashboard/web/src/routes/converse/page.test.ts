import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';

// 对话页的外部依赖：GET /api/config(模型下拉)与 WS /ws/converse(streamConverse)。
vi.mock('$lib/api', async (orig) => {
	const real = await orig<typeof import('$lib/api')>();
	return { ...real, api: { get: vi.fn().mockResolvedValue({ providers: {} }), post: vi.fn(), del: vi.fn() } };
});

type Handlers = { onError: (code: string) => void };
const streamConverse = vi.fn();
vi.mock('$lib/ws', async (orig) => {
	const real = await orig<typeof import('$lib/ws')>();
	return { ...real, streamConverse: (...a: unknown[]) => streamConverse(...a) };
});

const toastError = vi.fn();
vi.mock('$lib/ui/toast', () => ({
	toast: { error: (...a: unknown[]) => toastError(...a), success: vi.fn(), warning: vi.fn(), info: vi.fn() }
}));

import Converse from './+page.svelte';
import { worldErrorMessage } from '$lib/worlds';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

async function sendAndFail(code: string) {
	streamConverse.mockImplementation((_body: unknown, handlers: Handlers) => handlers.onError(code));
	const { container } = render(Converse);
	await settle();
	const box = container.querySelector('textarea') as HTMLTextAreaElement;
	await fireEvent.input(box, { target: { value: 'hi' } });
	await settle();
	const send = [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === '发送')!;
	await fireEvent.click(send);
	await settle();
}

describe('/converse onError 走世界码的中文提示（裁定 R59 I-2）', () => {
	beforeEach(() => {
		streamConverse.mockReset();
		toastError.mockReset();
	});

	it('endpoint_changed → 与 remember / recall 同一份中文提示', async () => {
		await sendAndFail('endpoint_changed');
		expect(toastError).toHaveBeenCalledWith(worldErrorMessage('endpoint_changed'));
	});

	it('world_not_found 也映射；未知码保持「对话出错」', async () => {
		await sendAndFail('world_not_found');
		expect(toastError).toHaveBeenCalledWith('世界不存在');
		toastError.mockReset();
		await sendAndFail('converse_failed');
		expect(toastError).toHaveBeenCalledWith('对话出错:converse_failed');
	});
});

// ── 第 5 期 Task 5.1 补充轮：其余写入入口置灰（spec §14，裁定 R109） ─────────────────
// 对话的一轮在回合末写入记忆(app.py 的 /ws/converse 走 pool.dashboard_write),所以「发送」是写入入口。
describe('/converse「发送」随世界状态置灰', () => {
	const FLAGS = {
		seed: false, read_only: false, reclaimable: false, open_mode: 'rw' as const,
		schema_behind: false, held_by_client: false
	};
	const sendBtn = (c: HTMLElement) =>
		[...c.querySelectorAll('button')].find((b) => b.textContent?.trim() === '发送') as HTMLButtonElement;
	const type = async (c: HTMLElement) => {
		await fireEvent.input(c.querySelector('textarea')!, { target: { value: 'hi' } });
		await settle();
	};

	beforeEach(async () => {
		const { page } = await import('$app/state');
		const { noteDefaultWorld, noteWorldStatus } = await import('$lib/world.svelte');
		(page as { url: URL }).url = new URL('http://localhost/converse?world=w1');
		noteDefaultWorld('default');
		noteWorldStatus('w1', null);
		streamConverse.mockReset();
	});

	it.each([
		['被占用', { held_by_client: true }, '这个世界正被客户端写入：写入已置灰，召回可用'],
		['只读', { seed: true, read_only: true, open_mode: 'ro' }, '只读世界（种子或复盘副本）：可以检视和召回，不能写入']
	])('%s：「发送」disabled 带 title，点了不开 /ws/converse', async (_n, over, reason) => {
		const { noteWorldStatus } = await import('$lib/world.svelte');
		noteWorldStatus('w1', { ...FLAGS, ...over } as typeof FLAGS);
		const { container } = render(Converse);
		await settle();
		await type(container);
		expect(sendBtn(container).disabled).toBe(true);
		expect(sendBtn(container).getAttribute('title')).toBe(reason);
		await fireEvent.click(sendBtn(container));
		await settle();
		expect(streamConverse).not.toHaveBeenCalled();
	});

	it('可写：「发送」可点、不带 title', async () => {
		const { noteWorldStatus } = await import('$lib/world.svelte');
		noteWorldStatus('w1', FLAGS);
		const { container } = render(Converse);
		await settle();
		await type(container);
		expect(sendBtn(container).disabled).toBe(false);
		expect(sendBtn(container).hasAttribute('title')).toBe(false);
	});
});
