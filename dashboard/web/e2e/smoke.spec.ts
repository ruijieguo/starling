import { test, expect } from '@playwright/test';

// Smoke: 新壳渲染 + 分组导航 + 当前页高亮(API 可能 401,只断言壳)。
test('shell renders grouped nav with active highlight', async ({ page }) => {
	await page.goto('/');
	// P2.n 后「Starling」出现两处(侧栏品牌块 + 面包屑),断品牌块。
	await expect(page.getByRole('link', { name: 'Memory Starling' })).toBeVisible();
	await expect(page.getByRole('button', { name: '观测' })).toBeVisible();
	await expect(page.getByRole('button', { name: '诊断' })).toBeVisible();
	await expect(page.getByRole('link', { name: '总览' })).toBeVisible();
	await expect(page.getByRole('link', { name: '评测' })).toBeVisible();
	await expect(page.getByRole('link', { name: '总览' })).toHaveAttribute('aria-current', 'page');
	// 分组眉标可折叠:点「诊断」收起后,评测链接消失,再点恢复。
	await page.getByRole('button', { name: '诊断' }).click();
	await expect(page.getByRole('link', { name: '评测' })).toBeHidden();
	await page.getByRole('button', { name: '诊断' }).click();
	await expect(page.getByRole('link', { name: '评测' })).toBeVisible();
});
