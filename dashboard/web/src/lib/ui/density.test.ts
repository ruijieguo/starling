import { describe, it, expect, beforeEach } from 'vitest';
import { pageSizeFor, applyDensity } from './density';

describe('pageSizeFor', () => {
	it('compact is denser than comfortable', () => {
		expect(pageSizeFor('compact')).toBeGreaterThan(pageSizeFor('comfortable'));
	});
});

describe('applyDensity', () => {
	beforeEach(() => {
		localStorage.clear();
		document.documentElement.removeAttribute('data-density');
	});

	it('writes <html data-density> and persists the choice', () => {
		applyDensity('compact');
		expect(document.documentElement.dataset.density).toBe('compact');
		expect(localStorage.getItem('starling_density')).toBe('compact');
	});

	it('overwrites a previously persisted choice', () => {
		applyDensity('compact');
		applyDensity('comfortable');
		expect(document.documentElement.dataset.density).toBe('comfortable');
		expect(localStorage.getItem('starling_density')).toBe('comfortable');
	});
});
