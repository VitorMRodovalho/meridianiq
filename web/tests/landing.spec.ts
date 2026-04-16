import { test, expect } from '@playwright/test';

test.describe('Landing Page (unauthenticated)', () => {
  test('shows hero section with CTA', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('main h1')).toContainText('intelligence standard');
    await expect(page.getByRole('link', { name: 'Get started free' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'View on GitHub' })).toBeVisible();
  });

  test('shows capability cards', async ({ page }) => {
    await page.goto('/');
    const heading = page.locator('main h2', { hasText: /\d+ Analysis Engines/ });
    await expect(heading).toBeAttached();
    await heading.scrollIntoViewIfNeeded();
    await expect(heading).toBeVisible();
    await expect(page.locator('main').getByText('DCMA 14-Point')).toBeVisible();
  });

  test('shows standards section', async ({ page }) => {
    await page.goto('/');
    const heading = page.locator('main h2', { hasText: 'Built on published standards' });
    await expect(heading).toBeAttached();
    await heading.scrollIntoViewIfNeeded();
    await expect(heading).toBeVisible();
  });

  test('shows key numbers', async ({ page }) => {
    await page.goto('/');
    // Key numbers are below the hero but above the fold for desktop
    await expect(page.locator('main').getByText('Analysis Engines').first()).toBeVisible();
    await expect(page.locator('main').getByText('Tests Passing')).toBeVisible();
  });

  test('"Get started free" links to login', async ({ page }) => {
    await page.goto('/');
    const link = page.getByRole('link', { name: 'Get started free' });
    await expect(link).toHaveAttribute('href', '/login');
  });
});
