import { describe, it, expect } from 'vitest';
import { missingFields } from './validate';

describe('missingFields', () => {
	it('flags empty model', () => {
		expect(missingFields({ model: '' }, { keyRequired: false, keySet: false, keyInput: '' })).toContain(
			'model'
		);
	});
	it('requires api_key only when keyRequired and not already set/typed', () => {
		expect(
			missingFields({ model: 'gpt' }, { keyRequired: true, keySet: false, keyInput: '' })
		).toContain('api_key');
		expect(
			missingFields({ model: 'gpt' }, { keyRequired: true, keySet: true, keyInput: '' })
		).toEqual([]);
		expect(
			missingFields({ model: 'gpt' }, { keyRequired: false, keySet: false, keyInput: '' })
		).toEqual([]);
	});
});
