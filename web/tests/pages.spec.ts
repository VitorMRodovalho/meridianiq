import { test, expect } from '@playwright/test';

test.describe('Public pages load without errors', () => {
  const routes: [string, string][] = [
    ['/', 'intelligence standard'],
    ['/login', 'Sign in'],
    ['/upload', 'Upload XER File'],
    ['/compare', 'Compare'],
    ['/forensic', 'Forensic'],
    ['/tia', 'Time Impact Analysis'],
    ['/contract', 'Contract Compliance'],
    ['/evm', 'EVM'],
    ['/risk', 'Risk'],
    ['/settings', 'Account Settings'],
    ['/demo', 'Sample Schedule Analysis'],
    ['/docs', 'Getting Started'],
    ['/org', 'Organizations'],
    ['/ips', 'IPS Reconciliation'],
    ['/recovery', 'Recovery Schedule Validation'],
    ['/milestones', 'Value Milestones'],
  ];

  for (const [route, expectedText] of routes) {
    test(`${route} loads and contains "${expectedText}"`, async ({ page }) => {
      await page.goto(route);
      await expect(page.locator('body')).not.toBeEmpty();
      // Look in main content area to avoid sidebar conflicts
      const target = route === '/login' ? page : page.locator('main');
      await expect(target.getByText(expectedText, { exact: false }).first()).toBeVisible();
    });
  }
});

test.describe('Login page', () => {
  test('shows all OAuth providers', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByText('Continue with Google')).toBeVisible();
    await expect(page.getByText('Continue with Microsoft')).toBeVisible();
    await expect(page.getByText('Continue with LinkedIn')).toBeVisible();
  });
});

test.describe('Upload page', () => {
  test('shows drag-and-drop zone', async ({ page }) => {
    await page.goto('/upload');
    await expect(page.locator('main').getByText('Drag and drop')).toBeVisible();
    await expect(page.locator('main').getByText('Browse files')).toBeVisible();
  });
});
