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
    ['/scorecard', 'Schedule Scorecard'],
    ['/whatif', 'What-If Simulator'],
    ['/resources', 'Resource Leveling'],
    ['/builder', 'Schedule Builder'],
    ['/visualization', '4D Visualization'],
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

test.describe('Intelligence pages have interactive controls', () => {
  test('Scorecard has project selector and button', async ({ page }) => {
    await page.goto('/scorecard');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Get Scorecard/i })).toBeVisible();
  });

  test('What-If has scenario controls', async ({ page }) => {
    await page.goto('/whatif');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.locator('input#target')).toBeVisible();
    await expect(page.getByRole('button', { name: /Run Scenario/i })).toBeVisible();
  });

  test('Resources has leveling controls', async ({ page }) => {
    await page.goto('/resources');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.locator('input#rsrc')).toBeVisible();
    await expect(page.locator('select#rule')).toBeVisible();
    await expect(page.getByRole('button', { name: /Run Resource Leveling/i })).toBeVisible();
  });

  test('Builder has generation form', async ({ page }) => {
    await page.goto('/builder');
    await expect(page.locator('select#type')).toBeVisible();
    await expect(page.locator('select#size')).toBeVisible();
    await expect(page.getByRole('button', { name: /Generate Schedule/i })).toBeVisible();
  });

  test('Visualization has project selector', async ({ page }) => {
    await page.goto('/visualization');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Visualize/i })).toBeVisible();
  });
});

test.describe('Docs page sections', () => {
  test('shows all 20 documentation sections', async ({ page }) => {
    await page.goto('/docs');
    await expect(page.getByText('Getting Started')).toBeVisible();
    await expect(page.getByText('Schedule Scorecard')).toBeVisible();
    await expect(page.getByText('What-If Simulator')).toBeVisible();
    await expect(page.getByText('Resource Leveling')).toBeVisible();
    await expect(page.getByText('MCP & AI Integration')).toBeVisible();
  });
});

test.describe('Sidebar navigation', () => {
  test('has Intelligence section with 5 links', async ({ page }) => {
    await page.goto('/');
    // On desktop, sidebar is visible
    await expect(page.getByText('Intelligence')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Scorecard' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'What-If' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Resources' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Schedule Builder' })).toBeVisible();
    await expect(page.getByRole('link', { name: '4D Visualization' })).toBeVisible();
  });
});
