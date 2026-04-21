// @ts-check
// Project: admin project (storageState = admin.json)
const { test, expect } = require('@playwright/test');

// ─── /users.html ────────────────────────────────────────────────────────────

test('admin: /users.html загружается со списком пользователей', async ({ page }) => {
  await page.goto('/users.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#usersTableBody tr:not(:has(.spinner-border))', {
    timeout: 15_000,
  });
  const rows = page.locator('#usersTableBody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
});

test('admin: в списке пользователей есть admin', async ({ page }) => {
  await page.goto('/users.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#usersTableBody tr:not(:has(.spinner-border))', {
    timeout: 15_000,
  });
  const bodyText = await page.locator('#usersTableBody').innerText();
  expect(bodyText).toContain('admin');
});

test('admin: кнопка «Добавить пользователя» открывает модалку', async ({ page }) => {
  await page.goto('/users.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#usersTableBody tr:not(:has(.spinner-border))', {
    timeout: 15_000,
  });
  await page.click('#btnAddUser');
  const modal = page.locator('#userModal');
  await expect(modal).toBeVisible({ timeout: 8_000 });
  await expect(page.locator('#userModalTitle')).toContainText(/пользователь/i);
});

test('admin: форма нового пользователя содержит поле логина', async ({ page }) => {
  await page.goto('/users.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#btnAddUser');
  await page.click('#btnAddUser');
  await expect(page.locator('#userModal #f_username')).toBeVisible({ timeout: 8_000 });
});

// ─── /projects.html ──────────────────────────────────────────────────────────

test('admin: /projects.html загружается со списком проектов', async ({ page }) => {
  await page.goto('/projects.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('table tbody tr', { timeout: 15_000 });
  const rows = page.locator('table tbody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
});

test('admin: в списке проектов есть «УЦН 2.0 2026»', async ({ page }) => {
  await page.goto('/projects.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('table tbody tr', { timeout: 15_000 });
  const bodyText = await page.locator('table tbody').innerText();
  expect(bodyText).toContain('УЦН 2.0 2026');
});

// ─── /logs.html ───────────────────────────────────────────────────────────────

test('admin: /logs.html загружается', async ({ page }) => {
  await page.goto('/logs.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  await page.waitForSelector('table, .alert, #logsTableBody, tbody', { timeout: 15_000 });
  await expect(page.locator('body')).toBeVisible();
});

// ─── /profile.html ───────────────────────────────────────────────────────────

test('admin: /profile.html показывает логин текущего пользователя', async ({ page }) => {
  await page.goto('/profile.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 15_000 });
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).toContain('admin');
});

test('профиль доступен через dropdown в navbar', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  const toggle = page.locator('#navbarUserToggle');
  await toggle.waitFor({ state: 'visible', timeout: 10_000 });
  await toggle.click();
  const profileLink = page.locator('a', { hasText: /профиль/i });
  await expect(profileLink).toBeVisible({ timeout: 5_000 });
  await profileLink.click();
  await expect(page).toHaveURL(/profile\.html/, { timeout: 8_000 });
});

// ─── RBAC: не-admin не попадает на admin-страницы ────────────────────────────
// (проверяется через auth.spec.js с реальным логином)
