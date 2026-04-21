// @ts-check
// Project: auth (no storageState — tests the actual login form and session behavior)
const { test, expect } = require('@playwright/test');
const { login, logout } = require('../helpers/auth');

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const ADMIN = {
  username: requireEnv('E2E_ADMIN_USERNAME'),
  password: requireEnv('E2E_ADMIN_PASSWORD'),
};
const USER = {
  username: requireEnv('E2E_USER_USERNAME'),
  password: requireEnv('E2E_USER_PASSWORD'),
};

// ─── Форма входа ────────────────────────────────────────────────────────────

test('открывается форма логина', async ({ page }) => {
  await page.goto('/login.html');
  await expect(page).toHaveTitle(/RTKS Tracker/);
  await expect(page.locator('#username')).toBeVisible();
  await expect(page.locator('#password')).toBeVisible();
  await expect(page.locator('#loginBtn')).toBeVisible();
});

test('неверный пароль — показывает ошибку', async ({ page }) => {
  await page.goto('/login.html');
  await page.fill('#username', 'admin');
  await page.fill('#password', 'wrongpassword');
  await page.click('#loginBtn');

  const errorBox = page.locator('#loginError');
  await expect(errorBox).toBeVisible({ timeout: 8_000 });
  await expect(errorBox).not.toHaveClass(/d-none/);
});

test('несуществующий пользователь — показывает ошибку', async ({ page }) => {
  await page.goto('/login.html');
  await page.fill('#username', 'ghost_user_xyz');
  await page.fill('#password', 'anypassword');
  await page.click('#loginBtn');

  await expect(page.locator('#loginError')).toBeVisible({ timeout: 8_000 });
});

// ─── Успешный вход ───────────────────────────────────────────────────────────

test('admin: успешный вход через форму → /index.html', async ({ page }) => {
  await login(page, ADMIN.username, ADMIN.password);
  await expect(page).toHaveURL(/\/index\.html/);
  await expect(page).toHaveTitle(/Проекты/);
});

test('non-admin: успешный вход через форму → /index.html', async ({ page }) => {
  await login(page, USER.username, USER.password);
  await expect(page).toHaveURL(/\/index\.html/);
});

// ─── Повторный вход ──────────────────────────────────────────────────────────

test('при живом токене /login.html → редирект на /index.html', async ({ page }) => {
  await login(page, ADMIN.username, ADMIN.password);
  await page.goto('/login.html');
  await expect(page).toHaveURL(/\/index\.html/, { timeout: 10_000 });
});

// ─── Выход ───────────────────────────────────────────────────────────────────

test('admin: выход очищает сессию → /login.html', async ({ page }) => {
  await login(page, ADMIN.username, ADMIN.password);
  await logout(page);
  await expect(page).toHaveURL(/\/login\.html/);

  // Без токена /index.html редиректит на login
  await page.goto('/index.html');
  await expect(page).toHaveURL(/\/login\.html/, { timeout: 10_000 });
});

test('non-admin: выход очищает сессию → /login.html', async ({ page }) => {
  await login(page, USER.username, USER.password);
  await logout(page);
  await expect(page).toHaveURL(/\/login\.html/);
});

// ─── RBAC: не-admin не попадает на admin-страницы ────────────────────────────

test('non-admin: /users.html → редирект (не admin)', async ({ page }) => {
  test.setTimeout(60_000);
  await login(page, USER.username, USER.password);
  await page.goto('/users.html');
  await page.waitForTimeout(3_000);
  const url = page.url();
  expect(url).not.toMatch(/users\.html/);
});

test('non-admin: /logs.html → редирект (не admin)', async ({ page }) => {
  test.setTimeout(60_000);
  await login(page, USER.username, USER.password);
  await page.goto('/logs.html');
  await page.waitForTimeout(3_000);
  const url = page.url();
  expect(url).not.toMatch(/logs\.html/);
});
