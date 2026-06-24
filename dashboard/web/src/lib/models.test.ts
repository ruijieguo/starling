import { describe, expect, it } from 'vitest';
import { roleConfigured, type Config } from './models';

const cfg: Config = {
	providers: {
		main: { provider: 'openai', model: 'm', base_url: '', key_set: true },
		nokey: { provider: 'openai', model: 'm', base_url: '', key_set: false }
	},
	roles: { extraction: 'main', embedding: 'nokey' }
};

describe('roleConfigured', () => {
	it('bound to a keyed provider → true', () => {
		expect(roleConfigured(cfg, 'extraction')).toBe(true);
	});
	it('bound to a keyless provider → false', () => {
		expect(roleConfigured(cfg, 'embedding')).toBe(false);
	});
	it('unbound role → false', () => {
		expect(roleConfigured(cfg, 'chat')).toBe(false);
	});
	it('missing config → null (unknown)', () => {
		expect(roleConfigured(null, 'extraction')).toBe(null);
		expect(roleConfigured(undefined, 'extraction')).toBe(null);
	});
	it('bound to a deleted provider → false (not crash)', () => {
		const c: Config = { providers: {}, roles: { extraction: 'gone' } };
		expect(roleConfigured(c, 'extraction')).toBe(false);
	});
});
