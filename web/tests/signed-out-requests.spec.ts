import { test, expect } from '@playwright/test';

// A signed-out visit must not call endpoints that need a session (#332).
// The computing banner used to poll /api/v1/projects/pending-statuses from
// the root layout on every page, which logged a 401 for every visitor.
test.describe('Signed-out visits', () => {
  for (const path of ['/', '/demo', '/upload']) {
    test(`${path} sends no request to pending-statuses`, async ({ page }) => {
      const hits: string[] = [];
      page.on('request', (request) => {
        if (request.url().includes('/api/v1/projects/pending-statuses')) hits.push(request.url());
      });

      await page.goto(path);
      await page.waitForLoadState('networkidle');

      expect(hits).toEqual([]);
    });
  }
});
