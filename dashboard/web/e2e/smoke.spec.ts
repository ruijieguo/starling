import { test, expect } from '@playwright/test';

// Smoke: app shell renders and the overview page mounts. (API may 401 without a
// running backend; we assert the shell + nav, not live data.)
test('shell renders with nav', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Starling')).toBeVisible();
  await expect(page.getByRole('link', { name: '总览' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Eval' })).toBeVisible();
});
