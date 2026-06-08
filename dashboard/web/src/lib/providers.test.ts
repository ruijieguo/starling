import { describe, it, expect } from 'vitest';
import { CHAT_PROVIDERS, EMBED_PROVIDERS, chatPreset, embedPreset } from './providers';

describe('provider presets', () => {
	it('chat presets include anthropic (native) with its base_url', () => {
		const a = chatPreset('anthropic');
		expect(a?.base_url).toBe('https://api.anthropic.com');
		expect(a?.needs_key).toBe(true);
	});
	it('embed presets EXCLUDE anthropic (no embeddings API)', () => {
		expect(EMBED_PROVIDERS.find((p) => p.id === 'anthropic')).toBeUndefined();
		expect(embedPreset('voyage')).toBeTruthy();
	});
	it('local providers (ollama) do not require a key', () => {
		expect(chatPreset('ollama')?.needs_key).toBe(false);
	});
	it('every preset has a stable id + label', () => {
		for (const p of [...CHAT_PROVIDERS, ...EMBED_PROVIDERS]) {
			expect(p.id).toBeTruthy();
			expect(p.label).toBeTruthy();
		}
	});
});
