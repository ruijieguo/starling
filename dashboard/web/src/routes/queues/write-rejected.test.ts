import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';
import { page } from '$app/state';
import { lastWsEvent, wsConn } from '$lib/health';
import { noteDefaultWorld, noteWorldStatus } from '$lib/world.svelte';

// 裁定 R113 I-1 的整条链：横幅取到「可写」之后客户端开了可写句柄(不发 WS 事件)，用户点「手动 Tick」，
// 后端回 409 world_held → 提示说清原因 → 横幅重取当前世界 → 显示「被占用」，按钮置灰。
// 用真的 $lib/api 与 $lib/worlds(只桩 fetch)：页面测试各自 mock 了 api，测不到 req 里的登记。
const toastError = vi.fn();
vi.mock('$lib/ui/toast', () => ({
	toast: { error: (...a: unknown[]) => toastError(...a), success: vi.fn(), warning: vi.fn(), info: vi.fn() }
}));

import Queues from './+page.svelte';
import WorldStatusBanner from '$lib/components/WorldStatusBanner.svelte';

const HELD = '这个世界正被客户端写入：写入已置灰，召回可用';
const QUEUES = { dispatch: { pending: 0 }, embedding_backlog: 0, vectors_by_status: {} };

const settle = async () => {
	for (let i = 0; i < 3; i++) {
		await tick();
		await Promise.resolve();
		await Promise.resolve();
	}
	await tick();
};

const row = (held: boolean) => ({
	name: 'w1', label: '', labels: {}, tenant: 'w1', created_at: '', open: true, holders: 0,
	last_write_at: null, statements: 0, snapshots: 0, snapshot_bytes: 0, archives: 0,
	archive_bytes: 0, auto_snapshot: { on_session: false, interval_hours: 0 },
	seed: false, read_only: false, reclaimable: false, retention_group: null,
	fork_of_world: null, fork_of_snapshot: null, open_mode: 'rw', schema_behind: false,
	held_by_client: held
});

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const tickButton = () =>
	[...document.body.querySelectorAll('button')].find((b) => b.textContent?.trim() === '手动 Tick') as
		| HTMLButtonElement
		| undefined;
const notices = () =>
	[...document.body.querySelectorAll('[role="status"]')].map((e) => e.textContent?.trim());

let held = false;
let calls: string[] = [];

beforeEach(() => {
	held = false;
	calls = [];
	toastError.mockReset();
	noteDefaultWorld('default');
	(page as { url: URL }).url = new URL('http://localhost/queues?world=w1');
	noteWorldStatus('w1', null);
	lastWsEvent.set(null);
	wsConn.set('closed');
	globalThis.fetch = vi.fn(async (path: string, init: RequestInit = {}) => {
		const method = init.method ?? 'GET';
		calls.push(`${method} ${path}`);
		if (method === 'GET' && path === '/api/worlds/w1') return json(row(held));
		if (method === 'GET' && path === '/api/w/w1/queues') return json(QUEUES);
		if (method === 'POST' && path === '/api/w/w1/tick') {
			held = true; // 客户端此刻已经占着写入：后端拒绝，之后的详情也给 held
			return json({ detail: 'world_held' }, 409);
		}
		return json({ detail: 'unexpected' }, 404);
	}) as unknown as typeof fetch;
});

describe('写入被拒后横幅重取，置灰立刻跟上（裁定 R113 I-1）', () => {
	it('/queues 手动 Tick 回 409 world_held：toast 说清原因，横幅重取后显示被占用，按钮置灰', async () => {
		render(WorldStatusBanner);
		render(Queues);
		await settle();
		const detailGets = () => calls.filter((c) => c === 'GET /api/worlds/w1').length;
		expect(detailGets()).toBe(1);
		expect(notices()).toEqual([]);
		expect(tickButton()!.disabled).toBe(false);

		await fireEvent.click(tickButton()!);
		await settle();
		expect(calls).toContain('POST /api/w/w1/tick');
		expect(toastError).toHaveBeenCalledWith(HELD);
		expect(detailGets()).toBe(2);
		expect(notices()).toEqual([HELD]);
		expect(tickButton()!.disabled).toBe(true);
		expect(tickButton()!.getAttribute('title')).toBe(HELD);
	});
});
