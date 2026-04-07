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
    ['/risk-register', 'Risk Register'],
    ['/lookahead', 'Look-Ahead Schedule'],
    ['/cashflow', 'Cash Flow Analysis'],
    ['/schedule', 'Schedule Viewer'],
    ['/calendar-validation', 'Calendar Validation'],
    ['/delay-attribution', 'Delay Attribution'],
    ['/anomalies', 'Anomaly Detection'],
    ['/root-cause', 'Root Cause Analysis'],
    ['/delay-prediction', 'Delay Prediction'],
    ['/duration-prediction', 'Duration Prediction'],
    ['/benchmarks', 'Benchmark Comparison'],
    ['/float-trends', 'Float Trends'],
    ['/reports', 'Reports Hub'],
    ['/optimizer', 'Schedule Optimizer'],
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

test.describe('New analysis pages have interactive controls', () => {
  test('Anomalies has project selector and button', async ({ page }) => {
    await page.goto('/anomalies');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Detect Anomalies/i })).toBeVisible();
  });

  test('Root Cause has project selector and activity input', async ({ page }) => {
    await page.goto('/root-cause');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.locator('input#activity')).toBeVisible();
    await expect(page.getByRole('button', { name: /Trace Root Cause/i })).toBeVisible();
  });

  test('Delay Prediction has model selector', async ({ page }) => {
    await page.goto('/delay-prediction');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.locator('select#model')).toBeVisible();
    await expect(page.getByRole('button', { name: /Predict Delays/i })).toBeVisible();
  });

  test('Duration Prediction has project selector', async ({ page }) => {
    await page.goto('/duration-prediction');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Predict Duration/i })).toBeVisible();
  });

  test('Benchmarks has compare and contribute buttons', async ({ page }) => {
    await page.goto('/benchmarks');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Compare/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Contribute/i })).toBeVisible();
  });

  test('Float Trends has dual project selectors', async ({ page }) => {
    await page.goto('/float-trends');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.locator('select#baseline')).toBeVisible();
    await expect(page.getByRole('button', { name: /Analyze/i })).toBeVisible();
  });

  test('Reports has check button', async ({ page }) => {
    await page.goto('/reports');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Check Reports/i })).toBeVisible();
  });

  test('Calendar Validation has project selector and validate button', async ({ page }) => {
    await page.goto('/calendar-validation');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.getByRole('button', { name: /Validate Calendars/i })).toBeVisible();
  });

  test('Optimizer has generation and population inputs', async ({ page }) => {
    await page.goto('/optimizer');
    await expect(page.locator('select#project')).toBeVisible();
    await expect(page.locator('input#gens')).toBeVisible();
    await expect(page.locator('input#pop')).toBeVisible();
    await expect(page.getByRole('button', { name: /Optimize/i })).toBeVisible();
  });
});

test.describe('Docs page sections', () => {
  test('shows documentation sections including new features', async ({ page }) => {
    await page.goto('/docs');
    await expect(page.getByText('Getting Started').first()).toBeVisible();
    await expect(page.getByText('Schedule Scorecard').first()).toBeVisible();
    await expect(page.getByText('What-If Simulator').first()).toBeVisible();
    await expect(page.getByText('Resource Leveling').first()).toBeVisible();
    await expect(page.getByText('MCP & AI Integration').first()).toBeVisible();
  });
});

test.describe('Sidebar navigation', () => {
  test('Intelligence section hidden when unauthenticated', async ({ page }) => {
    await page.goto('/');
    // Auth-required sections are hidden for unauthenticated users
    await expect(page.locator('aside').getByText('Intelligence')).not.toBeVisible();
  });
});
