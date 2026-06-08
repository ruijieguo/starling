import { describe, it, expect } from 'vitest';
import { pageSizeFor } from './density';

describe('pageSizeFor', () => {
	it('compact is denser than comfortable', () => {
		expect(pageSizeFor('compact')).toBeGreaterThan(pageSizeFor('comfortable'));
	});
});
