import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Admin Portal Accessibility', () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('a11y check: Login Page', async ({ page }) => {
    await page.locator('text="Staff sign in"').waitFor();
    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('a11y check: Admin Dashboard, Users, Inventory', async ({ page }) => {
    // 1. Login
    await page.locator('text="Staff sign in"').waitFor();
    await page.locator('input[name="email"]').fill('admin@blueharbor.local');
    await page.locator('input[name="password"]').fill('LocalTestAdmin!2026');
    await page.locator('button[type="submit"]').click();

    // 2. Navigation / Dashboard
    await expect(page.locator('text="Dashboard"').first().or(page.locator('text="Command center"').first())).toBeVisible({ timeout: 15000 });
    let scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);

    // 3. Buyers / Users
    await page.locator('button:has-text("Buyers")').click();
    await page.waitForTimeout(1000); // Wait for content
    scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);

    // 4. Inventory / Products
    await page.locator('button:has-text("Products")').click();
    await page.waitForTimeout(1000); // Wait for content
    scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);

    // 5. Settings / System Logs (if available, using a generic navigation)
    // If not visible, we ignore.
    const logsBtn = page.locator('button:has-text("Settings")');
    if (await logsBtn.isVisible()) {
      await logsBtn.click();
      await page.waitForTimeout(1000); // Wait for content
      scanResults = await new AxeBuilder({ page }).analyze();
      expect(scanResults.violations).toEqual([]);
    }
  });

  test('a11y check: invalid login state (error accessibility)', async ({ page }) => {
    await page.locator('input[name="email"]').fill('wrong@example.com');
    await page.locator('input[name="password"]').fill('wrong123456');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.admin-error')).toBeVisible({ timeout: 15000 });
    const scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);
  });
});
