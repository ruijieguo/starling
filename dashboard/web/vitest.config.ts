import { fileURLToPath } from 'node:url';
import { defineConfig, configDefaults } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
	plugins: [svelte()],
	resolve: {
		conditions: ['browser'],
		// 这里用的是裸 svelte() 而非 sveltekit(),所以 $lib 别名不会自动带进来。
		// 既有测试全走相对路径,一直没暴露;但路由页(+page.svelte)内部一律用 $lib/,
		// 不补这个别名就没法给任何一个页面写组件测试。
		alias: { $lib: fileURLToPath(new URL('./src/lib', import.meta.url)) }
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
