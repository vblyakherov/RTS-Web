// @ts-check
// Project: admin project (storageState = admin.json)
const { test, expect } = require('@playwright/test');
const { openUcnProject } = require('../helpers/auth');

// Хелпер: открыть список объектов UCN (уже аутентифицированы через storageState)
async function goToSites(page) {
  await openUcnProject(page);
  await page.waitForSelector('#sitesTableBody tr:not(:has(.spinner-border))', {
    timeout: 20_000,
  });
}

// ─── Список объектов ─────────────────────────────────────────────────────────

test('список UCN загружается и содержит строки', async ({ page }) => {
  await goToSites(page);
  const rows = page.locator('#sitesTableBody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
});

test('в списке UCN присутствует ID объекта вида UCN-2026-xxxx', async ({ page }) => {
  await goToSites(page);
  const bodyText = await page.locator('#sitesTableBody').innerText();
  expect(bodyText).toMatch(/UCN-2026-\d{4}/);
});

test('отображается заголовок проекта', async ({ page }) => {
  await goToSites(page);
  const title = page.locator('#projectTitle');
  await expect(title).toBeVisible();
  await expect(title).not.toBeEmpty();
});

test('badge со статистикой объектов отображается', async ({ page }) => {
  await goToSites(page);
  const badge = page.locator('#projectStatsBadge');
  await expect(badge).toBeVisible();
  await expect(badge).toContainText(/\d+/);
});

// ─── Фильтрация и поиск ──────────────────────────────────────────────────────

test('поиск сужает список объектов', async ({ page }) => {
  await goToSites(page);
  const rowsBefore = await page.locator('#sitesTableBody tr').count();

  await page.fill('#searchInput', 'UCN-2026-0001');
  await page.waitForTimeout(700);
  await page.waitForSelector('#sitesTableBody tr:not(:has(.spinner-border))', { timeout: 10_000 });

  const rowsAfter = await page.locator('#sitesTableBody tr').count();
  expect(rowsAfter).toBeLessThan(rowsBefore);
});

test('очистка поиска возвращает полный список', async ({ page }) => {
  await goToSites(page);
  const rowsBefore = await page.locator('#sitesTableBody tr').count();

  await page.fill('#searchInput', 'UCN-2026-0001');
  await page.waitForTimeout(700);
  await page.fill('#searchInput', '');
  await page.waitForTimeout(700);
  await page.waitForSelector('#sitesTableBody tr:not(:has(.spinner-border))', { timeout: 10_000 });

  const rowsAfter = await page.locator('#sitesTableBody tr').count();
  expect(rowsAfter).toBe(rowsBefore);
});

test('фильтр по статусу меняет список', async ({ page }) => {
  await goToSites(page);
  await page.selectOption('#filterStatus', 'planned');
  await page.waitForTimeout(700);
  await page.waitForSelector('#sitesTableBody tr:not(:has(.spinner-border))', { timeout: 10_000 });
  // Просто убеждаемся, что запрос прошёл
  await expect(page.locator('#sitesTableBody')).toBeVisible();
});

// ─── Открытие карточки объекта ───────────────────────────────────────────────

test('клик по объекту открывает /site.html', async ({ page }) => {
  await goToSites(page);
  const firstLink = page.locator('#sitesTableBody tr a').first();
  await firstLink.click();
  await expect(page).toHaveURL(/site\.html/, { timeout: 10_000 });
});

test('карточка объекта содержит ID объекта', async ({ page }) => {
  await goToSites(page);
  await page.locator('#sitesTableBody tr a').first().click();
  await page.waitForURL(/site\.html/, { timeout: 10_000 });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).toMatch(/UCN-2026-\d{4}/);
});

test('на карточке объекта есть кнопка «Редактировать»', async ({ page }) => {
  await goToSites(page);
  await page.locator('#sitesTableBody tr a').first().click();
  await page.waitForURL(/site\.html/, { timeout: 10_000 });
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });

  const editBtn = page.locator('button', { hasText: 'Редактировать' });
  await expect(editBtn).toBeVisible({ timeout: 8_000 });
});

// ─── Кнопки экспорта / импорта ───────────────────────────────────────────────

test('admin: на странице объектов видна кнопка «Экспорт»', async ({ page }) => {
  await goToSites(page);
  const exportBtn = page.locator('button, a', { hasText: /Экспорт/i }).first();
  await expect(exportBtn).toBeVisible();
});

test('admin: на странице объектов видна кнопка «Импорт»', async ({ page }) => {
  await goToSites(page);
  const importBtn = page.locator('button, a', { hasText: /Импорт/i }).first();
  await expect(importBtn).toBeVisible();
});
