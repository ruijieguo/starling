import { describe, it, expect } from 'vitest';
import { createQuery } from './query.svelte';

describe('createQuery', () => {
	it('moves through loading → data', async () => {
		const q = createQuery(async () => 42);
		expect(q.data).toBe(null);
		const p = q.refetch();
		expect(q.loading).toBe(true);
		await p;
		expect(q.loading).toBe(false);
		expect(q.data).toBe(42);
		expect(q.error).toBe(null);
	});
	it('captures errors as ApiError', async () => {
		const q = createQuery(async () => {
			throw new Error('boom');
		});
		await q.refetch();
		expect(q.error?.message).toContain('boom');
		expect(q.data).toBe(null);
	});
	it('drops a stale refetch — only the latest result wins', async () => {
		let resolveFirst!: (v: number) => void;
		const first = new Promise<number>((r) => (resolveFirst = r));
		let call = 0;
		const q = createQuery(() => (call++ === 0 ? first : Promise.resolve(2)));
		const p1 = q.refetch(); // gen 1, pends on `first`
		await q.refetch(); // gen 2, resolves to 2
		resolveFirst(1); // resolve the stale gen-1 fetch afterwards
		await p1;
		expect(q.data).toBe(2); // stale 1 dropped
	});
});
