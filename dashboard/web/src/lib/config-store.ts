import { writable } from 'svelte/store';
// Shared LLM-configured lamp state: null=unknown, true=configured, false=not.
export const llmConfigured = writable<boolean | null>(null);
