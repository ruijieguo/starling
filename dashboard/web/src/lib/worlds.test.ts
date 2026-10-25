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

describe('错误文案', () => {
	it('已知码与兜底', () => {
		expect(worldErrorMessage('ingest_busy')).toContain('摄入');
		expect(worldErrorMessage('insufficient_disk')).toContain('3 倍');
		expect(worldErrorMessage('weird')).toBe('操作失败：weird');
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
