import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Buyer Portal Accessibility', () => {
  test.setTimeout(120000);
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('a11y check: Login Page', async ({ page }) => {
    await page.locator('text="Sign in to continue"').waitFor();
    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('a11y check: Buyer Dashboard, Catalog, Documents, Orders', async ({ page }) => {
    // 1. Login
    await page.locator('text="Sign in to continue"').waitFor();
    await page.locator('input[name="email"]').fill('demo@blueharbor.local');
    await page.locator('input[name="password"]').fill('DemoPassword!2026');
    await page.locator('button[type="submit"]').click();

    // 2. Profile / Dashboard
    await expect(page.locator('text="Overview"').first()).toBeVisible({ timeout: 15000 });
    let scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);

    await page.locator('button:has-text("Profile & Compliance")').click();
    await page.waitForTimeout(1000);
    scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);

    // 3. Catalogue
    await page.locator('button:has-text("Marketplace")').click();
    await expect(page.locator('text="Find your next catch."')).toBeVisible();
    scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);

    // 4. View a Product details
    const productButton = page.locator('button:has-text("Reserve")').first();
    if (await productButton.isVisible()) {
      await productButton.click();
      await expect(page.locator('text="Confirm Order"')).toBeVisible();
      scanResults = await new AxeBuilder({ page }).analyze();
      expect(scanResults.violations).toEqual([]);
      // Cancel reservation
      await page.keyboard.press('Escape');
    }

    // 5. Orders and Shipping/Tracking
    // The dashboard usually has the orders list, we scan the whole page.
    await page.locator('button:has-text("Overview")').click();
    await expect(page.locator('text="Overview"').first()).toBeVisible();

    // Check if there are orders to view
    const viewOrderButton = page.locator('button:has-text("Track Shipment")').first();
    if (await viewOrderButton.isVisible()) {
      await viewOrderButton.click();
      scanResults = await new AxeBuilder({ page }).analyze();
      expect(scanResults.violations).toEqual([]);
      await page.keyboard.press('Escape');
    }

  });

  test('a11y check: invalid login state (error accessibility)', async ({ page }) => {
    await page.locator('input[name="email"]').fill('wrong@example.com');
    await page.locator('input[name="password"]').fill('wrong123456');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.inline-error')).toBeVisible({ timeout: 15000 });
    const scanResults = await new AxeBuilder({ page }).analyze();
    expect(scanResults.violations).toEqual([]);
  });
});
