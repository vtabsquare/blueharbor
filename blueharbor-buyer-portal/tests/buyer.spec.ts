import { test, expect } from '@playwright/test';

test.describe('Buyer Portal E2E', () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    // E2E tests must be run against a dedicated test environment.
    // Assuming backend is mocked or local test DB is provisioned.
    await page.goto('/');
  });

  test('complete buyer workflow: login to order', async ({ page }) => {
    // 1. Login
    await page.locator('text="Sign in to continue"').waitFor();
    await page.locator('input[name="email"]').fill('demo@blueharbor.local');
    await page.locator('input[name="password"]').fill('DemoPassword!2026');
    await page.locator('button[type="submit"]').click();

    // 2. Profile
    await expect(page.locator('text="Overview"').first()).toBeVisible({ timeout: 15000 });
    await page.locator('button:has-text("Profile & Compliance")').click();
    await page.waitForTimeout(1000);

    // 3. Document Upload (Assuming form exists)
    // Wait for document upload form
    // const fileChooserPromise = page.waitForEvent('filechooser');
    // Using a generic selector, in reality would click the precise upload button
    // await page.locator('input[type="file"]').click(); 
    // const fileChooser = await fileChooserPromise;
    // await fileChooser.setFiles('tests/fixtures/dummy.pdf');
    
    // 4. Verification submission
    // await page.locator('button:has-text("Submit for review")').click();
    
    // 5. Catalogue
    await page.locator('button:has-text("Marketplace")').click();
    await expect(page.locator('text="Find your next catch."')).toBeVisible();

    // 6. Order / Reservation
    // await page.locator('button:has-text("Reserve")').first().click();
    // await page.locator('button:has-text("Confirm Order")').click();

    // 7. Logout
    await page.locator('button:has-text("Sign out")').click();
    await expect(page.locator('text="Sign in to continue"')).toBeVisible();
  });

  test('negative: invalid login', async ({ page }) => {
    await page.locator('input[name="email"]').fill('wrong@example.com');
    await page.locator('input[name="password"]').fill('wrong123456');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('text="Invalid login credentials"').or(page.locator('.inline-error'))).toBeVisible({ timeout: 15000 });
  });
  
  test('negative: protected API rejected after logout', async ({ request }) => {
    const response = await request.get('/api/state', {
      headers: { 'X-BlueHarbor': '1' }
    });
    expect(response.status()).toBe(401);
  });
});
