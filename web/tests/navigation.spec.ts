import { test, expect } from '@playwright/test';

test.describe('Navigation (desktop)', () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test('sidebar has public nav links (unauthenticated)', async ({ page }) => {
    await page.goto('/');
    const sidebar = page.locator('aside');
    for (const label of ['Dashboard', 'Upload', 'Projects', 'Settings']) {
      await expect(sidebar.getByText(label, { exact: true })).toBeVisible();
    }
    // Auth-required sections should be hidden
    await expect(sidebar.getByText('Schedule', { exact: true })).not.toBeVisible();
    await expect(sidebar.getByText('Enterprise', { exact: true })).not.toBeVisible();
  });

  test('sidebar shows MeridianIQ branding', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('aside h1')).toContainText('MeridianIQ');
    await expect(page.locator('aside').getByText('v3.2.0')).toBeVisible();
  });

  test('nav links navigate correctly', async ({ page }) => {
    await page.goto('/');
    await page.locator('aside').getByText('Upload', { exact: true }).click();
    await expect(page).toHaveURL('/upload');
    await expect(page.locator('main').getByText('Upload XER File')).toBeVisible();
  });
});

test.describe('Navigation (mobile)', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test('sidebar is hidden by default', async ({ page }) => {
    await page.goto('/');
    const sidebar = page.locator('aside');
    // Sidebar should be off-screen (translated left)
    await expect(sidebar).toHaveClass(/\-translate-x-full/);
  });

  test('hamburger opens and close button closes sidebar', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Open menu').click();
    const sidebar = page.locator('aside');
    await expect(sidebar).toHaveClass(/translate-x-0/);

    // Close via X button
    await sidebar.getByLabel('Close menu').click();
    await expect(sidebar).toHaveClass(/\-translate-x-full/);
  });

  test('clicking a nav link closes sidebar and navigates', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Open menu').click();
    await page.locator('aside').getByText('Upload', { exact: true }).click();
    await expect(page).toHaveURL('/upload');
  });
});
