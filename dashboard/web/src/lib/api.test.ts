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
