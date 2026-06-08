import { test, expect } from '@playwright/test';

// Smoke: 新壳渲染 + 分组导航 + 当前页高亮(API 可能 401,只断言壳)。
test('shell renders grouped nav with active highlight', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('Starling')).toBeVisible();
	await expect(page.getByText('观测', { exact: true })).toBeVisible();
	await expect(page.getByText('诊断', { exact: true })).toBeVisible();
	await expect(page.getByRole('link', { name: '总览' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Eval' })).toBeVisible();
	await expect(page.getByRole('link', { name: '总览' })).toHaveAttribute('aria-current', 'page');
});
