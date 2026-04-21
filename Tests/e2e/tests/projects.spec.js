// @ts-check
// Project: admin project (storageState = admin.json)
const { test, expect } = require('@playwright/test');
const { openUcnProject } = require('../helpers/auth');

// ─── Экран выбора проекта ────────────────────────────────────────────────────

test('admin: на /index.html отображаются плитки проектов', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#projectsState h5', { timeout: 15_000 });
  const tiles = page.locator('#projectsState h5');
  const count = await tiles.count();
  expect(count).toBeGreaterThanOrEqual(3);
});

test('admin: на /index.html видна кнопка «Управление проектами»', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  const btn = page.locator('#manageProjectsBtn');
  await expect(btn).toBeVisible();
});

test('admin: на /index.html в navbar есть «Пользователи» и «Логи»', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  await expect(page.locator('a[href="/users.html"]')).toBeVisible();
  await expect(page.locator('a[href="/logs.html"]')).toBeVisible();
});

test('admin: на /index.html нет пункта «Объекты» в navbar', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  const sitesLinks = page.locator('.navbar-nav .nav-link', { hasText: 'Объекты' });
  await expect(sitesLinks).not.toBeVisible();
});

test('все три ожидаемых проекта присутствуют', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#projectsState h5', { timeout: 15_000 });
  const text = await page.locator('#projectsState').innerText();
  expect(text).toContain('УЦН 2.0 2026');
  expect(text).toContain('ТСПУ');
  expect(text).toContain('Стройка ЦОД');
});

// ─── Переход в UCN-модуль ────────────────────────────────────────────────────

test('клик по UCN-проекту → переход на /sites.html', async ({ page }) => {
  await openUcnProject(page);
  await expect(page).toHaveURL(/sites\.html/);
  await expect(page.locator('#projectTitle')).toBeVisible({ timeout: 10_000 });
});

test('внутри UCN-модуля появляется «Объекты» в navbar', async ({ page }) => {
  await openUcnProject(page);
  const sitesLink = page.locator('#navbar-container .nav-link', { hasText: 'Объекты' });
  await expect(sitesLink).toBeVisible({ timeout: 10_000 });
});

test('внутри UCN-модуля для admin видны «Справочники»', async ({ page }) => {
  await openUcnProject(page);
  // «Справочники» — button.nav-link.dropdown-toggle, не <a>
  const refBtn = page.locator('#navbar-container button.nav-link', { hasText: 'Справочники' });
  await expect(refBtn).toBeVisible({ timeout: 10_000 });
});

test('кнопка «К выбору проектов» возвращает на /index.html', async ({ page }) => {
  await openUcnProject(page);
  await page.locator('a[href="/index.html"]').first().click();
  await expect(page).toHaveURL(/\/index\.html/);
});

// ─── non-admin: проверки без отдельного storageState ────────────────────────
// Эти проверки вынесены в auth.spec.js, где используется реальный вход через форму.

test('non-admin: НЕ видит кнопку «Управление проектами»', async ({ page, browser }) => {
  // Создаём контекст без storageState (анонимный); роль non-admin проверяется отдельно.
  // Этот тест пропускается в рамках admin project
  test.skip();
});
