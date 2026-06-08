import { describe, it, expect } from 'vitest';
import { cycleTheme, resolveTheme } from './theme';

describe('theme', () => {
	it('cycles light → dark → system → light', () => {
		expect(cycleTheme('light')).toBe('dark');
		expect(cycleTheme('dark')).toBe('system');
		expect(cycleTheme('system')).toBe('light');
	});
	it('resolves explicit modes directly', () => {
		expect(resolveTheme('light')).toBe('light');
		expect(resolveTheme('dark')).toBe('dark');
	});
});
