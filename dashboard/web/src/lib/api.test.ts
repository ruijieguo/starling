import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './api';
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
	it('throws on non-ok', async () => {
		globalThis.fetch = vi.fn(async () => new Response('', { status: 401 })) as any;
		await expect(api.get('/api/overview')).rejects.toThrow('401');
	});
});
