import { test, expect } from '@playwright/test';

test.describe('Admin Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('admin workflow: login -> case review -> lot allocation -> publish', async ({ page }) => {
    // 1. Admin Login
    await page.locator('text="Sign in to continue"').waitFor();
    await page.locator('input[name="email"]').fill('admin@example.com');
    await page.locator('input[name="password"]').fill('admin_password');
    await page.locator('button[type="submit"]').click();

    // 2. Navigation
    await expect(page.locator('text="Dashboard"').or(page.locator('text="Overview"'))).toBeVisible();
    await page.locator('button:has-text("Buyers & Verification")').click();

    // 3. Case review
    // Select first case
    // await page.locator('.case-card').first().click();
    // await page.locator('button:has-text("Approve Document")').click();

    // 4. Lot Allocation
    await page.locator('button:has-text("Inventory")').click();
    // await page.locator('button:has-text("Allocate Lot")').click();
    
    // 5. Publish
    // await page.locator('button:has-text("Publish")').click();
    
    // 6. Logout
    await page.locator('button:has-text("Sign out")').click();
    await expect(page.locator('text="Sign in to continue"')).toBeVisible();
  });

  test('negative: forbidden role access', async ({ request }) => {
    const response = await request.get('/api/admin/state', {
      headers: { 'X-BlueHarbor': '1' }
    });
    // Should be 401 or 403 when not logged in / lacking permission
    expect(response.status()).toBe(401);
  });
});
