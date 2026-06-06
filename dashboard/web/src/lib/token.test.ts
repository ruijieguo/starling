import { describe, it, expect, beforeEach } from 'vitest';
import { adoptTokenFromHash, getToken } from './token';

beforeEach(() => {
	localStorage.clear();
	history.replaceState(null, '', '/');
});

describe('adoptTokenFromHash', () => {
	it('adopts #token= and strips it from the URL', () => {
		history.replaceState(null, '', '/#token=abc123');
		adoptTokenFromHash();
		expect(getToken()).toBe('abc123');
		expect(location.hash).toBe('');
	});
	it('no-op without a token fragment', () => {
		history.replaceState(null, '', '/#other=1');
		adoptTokenFromHash();
		expect(getToken()).toBe('');
	});
});
