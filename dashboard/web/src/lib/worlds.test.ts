import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as tok from './token';
import { ApiError } from './api';
import {
	worldsApi, isValidWorldName, formatBytes, worldErrorMessage, apiDetail
} from './worlds';

let calls: Array<[string, RequestInit]> = [];
beforeEach(() => {
	calls = [];
	vi.spyOn(tok, 'getToken').mockReturnValue('');
	globalThis.fetch = vi.fn(async (p: string, init: RequestInit) => {
		calls.push([p, init]);
		return new Response(JSON.stringify({ ok: 1 }), { status: 200 });
	}) as unknown as typeof fetch;
});

describe('世界名校验（与后端 is_valid_world_name 同一规则）', () => {
	it.each(['default', 'sim-1', 'a_b', '0abc', 'a'.repeat(32)])('接受 %s', (n) =>
		expect(isValidWorldName(n)).toBe(true));
	it.each(['', '-x', 'Up', 'a b', '../x', 'a/b', 'a'.repeat(33)])('拒绝 %s', (n) =>
		expect(isValidWorldName(n)).toBe(false));
});

describe('formatBytes', () => {
	it('格式化', () => {
		expect(formatBytes(0)).toBe('0 B');
		expect(formatBytes(1536)).toBe('1.5 KB');
		expect(formatBytes(57 * 2 ** 20)).toBe('57.0 MB');
		expect(formatBytes(2.4 * 2 ** 30)).toBe('2.4 GB');
	});
});

describe('worldsApi 路径与方法', () => {
	it('list/create/activate/remove/snapshot', async () => {
		await worldsApi.list();
		await worldsApi.create('sim-1', '模拟');
		await worldsApi.activate('sim-1');
		await worldsApi.remove('sim-1', 'sim-1');
		await worldsApi.snapshots('sim-1');
		await worldsApi.snapshot('sim-1', 'n');
		await worldsApi.removeSnapshot('sim-1', 'id 1');
		expect(calls.map(([p, i]) => `${i.method ?? 'GET'} ${p}`)).toEqual([
			'GET /api/worlds',
			'POST /api/worlds',
			'POST /api/worlds/sim-1/activate',
			'DELETE /api/worlds/sim-1?confirm=sim-1',
			'GET /api/worlds/sim-1/snapshots',
			'POST /api/worlds/sim-1/snapshots',
			'DELETE /api/worlds/sim-1/snapshots/id%201'
		]);
		expect(JSON.parse(String(calls[1][1].body))).toEqual({ name: 'sim-1', label: '模拟' });
		expect(JSON.parse(String(calls[5][1].body))).toEqual({ note: 'n' });
	});
});

describe('worldsApi 回滚与清理归档（W3）', () => {
	it('rollback：POST /rollback，body 显式带 mode=discard_after（确认框文案描述的正是语义 A）', async () => {
		await worldsApi.rollback('sim-1', '20261026T120000Z-ab12', 'sim-1');
		expect(calls.map(([p, i]) => `${i.method ?? 'GET'} ${p}`)).toEqual([
			'POST /api/worlds/sim-1/rollback'
		]);
		expect(JSON.parse(String(calls[0][1].body))).toEqual({
			snapshot_id: '20261026T120000Z-ab12',
			confirm: 'sim-1',
			mode: 'discard_after'
		});
	});

	it('purgeArchives：DELETE /archives?confirm=<编码后的确认名>', async () => {
		await worldsApi.purgeArchives('sim-1', 'sim-1');
		await worldsApi.purgeArchives('sim-1', 'a b&c');
		expect(calls.map(([p, i]) => `${i.method ?? 'GET'} ${p}`)).toEqual([
			'DELETE /api/worlds/sim-1/archives?confirm=sim-1',
			'DELETE /api/worlds/sim-1/archives?confirm=a%20b%26c'
		]);
		expect(calls[0][1].body).toBeUndefined();
	});

	it('purgeArchives 的超时放宽到 120s（要排队等快照或回滚持有的管理锁）', async () => {
		vi.useFakeTimers();
		try {
			globalThis.fetch = vi.fn(
				(_p: string, init: RequestInit) =>
					new Promise((_resolve, reject) => {
						init.signal?.addEventListener('abort', () =>
							reject(new DOMException('aborted', 'AbortError'))
						);
					})
			) as unknown as typeof fetch;
			const caught = worldsApi.purgeArchives('sim-1', 'sim-1').catch((e) => e as ApiError);
			let settled = false;
			void caught.then(() => (settled = true));
			await vi.advanceTimersByTimeAsync(119_000); // 越过默认 15s:仍在等
			expect(settled).toBe(false);
			await vi.advanceTimersByTimeAsync(2_000);
			const err = (await caught) as ApiError;
			expect(err).toBeInstanceOf(ApiError);
			expect(err.message).toContain('120');
		} finally {
			vi.useRealTimers();
		}
	});

	it('rollback 的超时放宽到 120s（默认 15s 不够复制快照 + 重建引擎）', async () => {
		vi.useFakeTimers();
		try {
			globalThis.fetch = vi.fn(
				(_p: string, init: RequestInit) =>
					new Promise((_resolve, reject) => {
						init.signal?.addEventListener('abort', () =>
							reject(new DOMException('aborted', 'AbortError'))
						);
					})
			) as unknown as typeof fetch;
			const caught = worldsApi.rollback('sim-1', 's1', 'sim-1').catch((e) => e as ApiError);
			let settled = false;
			void caught.then(() => (settled = true));
			await vi.advanceTimersByTimeAsync(119_000); // 越过默认 15s 与切换的 60s:仍在等
			expect(settled).toBe(false);
			await vi.advanceTimersByTimeAsync(2_000); // 越过 120s → 中断
			const err = (await caught) as ApiError;
			expect(err).toBeInstanceOf(ApiError);
			expect(err.message).toContain('120');
		} finally {
			vi.useRealTimers();
		}
	});
});

describe('错误文案', () => {
	it('回滚新增的两个错误码有中文文案', () => {
		expect(worldErrorMessage('snapshot_corrupt')).toBe('快照文件损坏或缺失，未做任何改动');
		expect(worldErrorMessage('rollback_mode_unsupported')).toBe('不支持的回滚方式');
	});
	it('已知码与兜底', () => {
		expect(worldErrorMessage('weird')).toBe('操作失败：weird');
	});
	it('切换与回滚共用的码:文案对两种语境都成立', () => {
		expect(worldErrorMessage('ingest_busy')).toBe(
			'后台任务或在途请求暂时停不下来，未做任何改动，请稍后再试'
		);
		expect(worldErrorMessage('world_open_failed')).toBe(
			'引擎打开失败，数据库未改动（切换时已留在原世界）；下一次写入、召回或在「队列」页手动 tick 时会自动重建，仍异常请查看服务日志'
		);
		expect(worldErrorMessage('insufficient_disk')).toBe(
			'磁盘空间不足：快照需要至少 3 倍于数据量、回滚需要至少 2 倍于快照大小的可用空间'
		);
		expect(worldErrorMessage('snapshot_failed')).toBe('文件操作失败，数据库未改动；详情见服务日志');
	});
	it('回滚的两个新码:world_in_use 与 rollback_reopen_failed', () => {
		expect(worldErrorMessage('world_in_use')).toBe(
			'该世界的数据库正被其他程序打开，未做任何改动；请关闭后重试'
		);
		expect(worldErrorMessage('rollback_reopen_failed')).toBe(
			'已回滚到快照，但引擎重开失败；页面即将刷新，下一次写入、召回或手动 tick 时会自动重建，仍异常请查看服务日志'
		);
	});
	it('snapshot_not_found（契约里 DELETE 快照的 404）有中文文案', () => {
		expect(worldErrorMessage('snapshot_not_found')).toBe('快照不存在');
	});
	it('租户不变式、切换窗口与服务器内部错误有中文文案', () => {
		expect(worldErrorMessage('world_tenant_mismatch')).toBe(
			'该世界的数据库里有其他租户的数据，拒绝打开'
		);
		expect(worldErrorMessage('world_switching')).toBe('正在切换世界，请稍后再试');
		expect(worldErrorMessage('internal_error')).toBe('服务器内部错误');
	});
	it.each(['constructor', 'toString', '__proto__', 'hasOwnProperty'])(
		'继承来的键 %s 不是错误码，走兜底而不是返回函数',
		(k) => {
			const msg = worldErrorMessage(k);
			expect(typeof msg).toBe('string');
			expect(msg).toBe(`操作失败：${k}`);
		}
	);
	it('从 ApiError 提取 detail', () => {
		expect(apiDetail(new ApiError(409, '/api/worlds', '409 world_exists'))).toBe('world_exists');
		expect(apiDetail(new Error('x'))).toBe('Error: x');
	});
});
