import { defineConfig, configDefaults } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
	plugins: [svelte()],
	resolve: {
		conditions: ['browser']
	},
	test: {
		environment: 'jsdom',
		globals: true,
		restoreMocks: true,
		setupFiles: ['@testing-library/svelte/vitest'],
		include: [...(configDefaults.include ?? []), '**/*.test.svelte.ts'],
		// Playwright e2e specs run under `playwright test`, not vitest.
		exclude: [...configDefaults.exclude, 'e2e/**']
	}
});
