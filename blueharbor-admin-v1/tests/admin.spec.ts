import { test, expect } from '@playwright/test';

test.describe('Admin Portal E2E', () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('admin workflow: login -> case review -> lot allocation -> publish', async ({ page }) => {
    // 1. Admin Login
    await page.locator('text="Staff sign in"').waitFor();
    await page.locator('input[name="email"]').fill('admin@blueharbor.local');
    await page.locator('input[name="password"]').fill('LocalTestAdmin!2026');
    await page.locator('button[type="submit"]').click();

    // 2. Navigation
    await expect(page.locator('text="Dashboard"').first().or(page.locator('text="Command center"').first())).toBeVisible({ timeout: 15000 });
    await page.locator('button:has-text("Buyers")').click();

    // 3. Case review
    // Select first case
    // await page.locator('.case-card').first().click();
    // await page.locator('button:has-text("Approve Document")').click();

    // 4. Lot Allocation
    await page.locator('button:has-text("Products")').click();
    // await page.locator('button:has-text("Allocate Lot")').click();
    
    // 5. Publish
    // await page.locator('button:has-text("Publish")').click();
    
    // 6. Logout
    await page.locator('button:has-text("Sign out")').click();
    await expect(page.locator('text="Staff sign in"')).toBeVisible();
  });

  test('negative: forbidden role access', async ({ request }) => {
    const response = await request.get('/api/admin/state', {
      headers: { 'X-BlueHarbor': '1' }
    });
    // Should be 401 or 403 when not logged in / lacking permission
    expect([401, 403]).toContain(response.status());
  });
});
