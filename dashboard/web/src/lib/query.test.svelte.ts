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
});
