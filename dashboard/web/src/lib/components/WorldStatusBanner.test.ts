import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render } from '@testing-library/svelte';
import { page } from '$app/state';
import { lastWsEvent } from '$lib/health';
import { noteDefaultWorld, noteWorldStatus, worldStatusOf } from '$lib/world.svelte';

// 横幅只有一个外部依赖：当前世界的详情(worldsApi.detail)。
const detail = vi.fn();
vi.mock('$lib/worlds', async (orig) => {
	const real = await orig<typeof import('$lib/worlds')>();
	return { ...real, worldsApi: { ...real.worldsApi, detail: (...a: unknown[]) => detail(...a) } };
});

import WorldStatusBanner from './WorldStatusBanner.svelte';

// 文案逐字照计划(docs/superpowers/plans/2026-11-06-memory-service-p2-p6.md Task 5.1)。故意不引用常量:改了文案这里要红。
const READ_ONLY = '只读世界（种子或复盘副本）：可以检视和召回，不能写入';
const HELD = '这个世界正被客户端写入：写入已置灰，召回可用';
const SCHEMA = '这个世界的库版本落后于当前 Starling，部分检视页可能报错';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

const at = (u: string) => {
	(page as { url: URL }).url = new URL(u, 'http://localhost');
};

const row = (name: string, over: Record<string, unknown> = {}) => ({
	name, label: '', labels: {}, tenant: name, created_at: '', open: true, holders: 0,
	last_write_at: null, statements: 0, snapshots: 0, snapshot_bytes: 0, archives: 0,
	archive_bytes: 0, auto_snapshot: { on_session: false, interval_hours: 0 },
	seed: false, read_only: false, reclaimable: false, retention_group: null,
	fork_of_world: null, fork_of_snapshot: null, open_mode: 'rw', schema_behind: false,
	held_by_client: false, ...over
});

const notices = (c: HTMLElement) =>
	[...c.querySelectorAll('[role="status"]')].map((e) => e.textContent?.trim());

beforeEach(() => {
	noteDefaultWorld('default');
	at('/statements?world=w1');
	lastWsEvent.set(null);
	noteWorldStatus('w1', null);
	detail.mockReset();
});

describe('WorldStatusBanner', () => {
	it.each([
		['open_mode 为 ro（可回收世界）', { open_mode: 'ro', reclaimable: true }],
		['read_only 为真', { read_only: true, open_mode: 'ro' }],
		['seed 为真', { seed: true, read_only: true }]
	])('只读：%s', async (_n, over) => {
		detail.mockResolvedValue(row('w1', over));
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(detail).toHaveBeenCalledWith('w1');
		expect(notices(container)).toEqual([READ_ONLY]);
	});

	it('被占用：held_by_client 为真', async () => {
		detail.mockResolvedValue(row('w1', { held_by_client: true }));
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(notices(container)).toEqual([HELD]);
	});

	it('schema 落后：schema_behind 为 true；null(读不出)不算', async () => {
		detail.mockResolvedValue(row('w1', { schema_behind: true }));
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(notices(container)).toEqual([SCHEMA]);
	});

	it('多种状态同时出现：每种各一条，依次为只读、被占用、schema 落后', async () => {
		detail.mockResolvedValue(
			row('w1', { reclaimable: true, open_mode: 'ro', held_by_client: true, schema_behind: true })
		);
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(notices(container)).toEqual([READ_ONLY, HELD, SCHEMA]);
	});

	it.each([
		['都不满足', { schema_behind: false }],
		['schema_behind 为 null', { schema_behind: null }]
	])('%s：什么都不渲染', async (_n, over) => {
		detail.mockResolvedValue(row('w1', over));
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(notices(container)).toEqual([]);
		expect(container.textContent?.trim()).toBe('');
	});

	it('详情取不到：不渲染，不抛', async () => {
		detail.mockRejectedValue(new Error('404 world_not_found'));
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(container.textContent?.trim()).toBe('');
	});

	it('把取到的状态登记给页面(worldStatusOf)，只认对应的世界', async () => {
		detail.mockResolvedValue(row('w1', { held_by_client: true }));
		render(WorldStatusBanner);
		await settle();
		expect(worldStatusOf('w1')?.held_by_client).toBe(true);
		expect(worldStatusOf('w2')).toBeNull();
	});

	it('换世界就重取，旧世界的状态不挂在新世界上', async () => {
		detail.mockImplementation(async (name: string) =>
			name === 'w1' ? row('w1', { held_by_client: true }) : row(name)
		);
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(notices(container)).toEqual([HELD]);
		at('/statements?world=w2');
		await settle();
		expect(detail).toHaveBeenLastCalledWith('w2');
		expect(notices(container)).toEqual([]);
	});

	it('当前世界的 world_changed 触发重取；别的世界的事件与纯读的 recall 不触发', async () => {
		detail.mockResolvedValue(row('w1'));
		const { container } = render(WorldStatusBanner);
		await settle();
		const calls = detail.mock.calls.length;
		lastWsEvent.set({ type: 'world_changed', world: 'w2', payload: {} });
		await settle();
		lastWsEvent.set({ type: 'recall', world: 'w1', payload: {} });
		await settle();
		expect(detail.mock.calls.length).toBe(calls);
		detail.mockResolvedValue(row('w1', { held_by_client: true }));
		lastWsEvent.set({ type: 'world_changed', world: 'w1', payload: {} });
		await settle();
		expect(detail.mock.calls.length).toBe(calls + 1);
		expect(notices(container)).toEqual([HELD]);
	});

	it('换页(路径变了)也重取一次：客户端关掉句柄不发事件', async () => {
		detail.mockResolvedValue(row('w1', { held_by_client: true }));
		const { container } = render(WorldStatusBanner);
		await settle();
		expect(notices(container)).toEqual([HELD]);
		detail.mockResolvedValue(row('w1'));
		at('/queues?world=w1');
		await settle();
		expect(notices(container)).toEqual([]);
	});
});
