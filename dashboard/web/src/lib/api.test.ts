import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api, ApiError } from './api';
import * as tok from './token';

beforeEach(() => {
	vi.spyOn(tok, 'getToken').mockReturnValue('secret');
	globalThis.fetch = vi.fn(
		async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 })
	) as unknown as typeof fetch;
});

describe('api', () => {
	it('attaches bearer token', async () => {
		await api.get('/api/overview');
		const [, init] = (globalThis.fetch as any).mock.calls[0];
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer secret');
	});
	it('honors per-request timeoutMs (LLM 路径放宽,默认 15s 不变)', async () => {
		vi.useFakeTimers();
		// fetch 挂起直到 signal abort——模拟慢后端。
		globalThis.fetch = vi.fn(
			(_p: string, init: RequestInit) =>
				new Promise((_resolve, reject) => {
					init.signal?.addEventListener('abort', () =>
						reject(new DOMException('aborted', 'AbortError'))
					);
				})
		) as any;
		const pending = api.post('/api/remember', { text: 'x' }, { timeoutMs: 120_000 });
		const caught = pending.catch((e) => e as ApiError);
		await vi.advanceTimersByTimeAsync(15_000); // 默认超时点:不应中断
		await vi.advanceTimersByTimeAsync(104_000); // 119s:仍未中断
		expect((globalThis.fetch as any).mock.calls.length).toBe(1);
		await vi.advanceTimersByTimeAsync(2_000); // 越过 120s → 中断
		const err = (await caught) as ApiError;
		expect(err).toBeInstanceOf(ApiError);
		expect(String(err.message)).toContain('120');
		vi.useRealTimers();
	});
	it('throws ApiError on non-ok with status + path', async () => {
		globalThis.fetch = vi.fn(
			async () => new Response(JSON.stringify({ detail: 'nope' }), { status: 401 })
		) as any;
		let err!: ApiError;
		await api.get('/api/overview').catch((e) => { err = e as ApiError; });
		expect(err).toBeInstanceOf(ApiError);
		expect(err.status).toBe(401);
		expect(err.isAuth).toBe(true);
		expect(err.path).toBe('/api/overview');
		expect(String(err.message)).toContain('nope');
	});
});
