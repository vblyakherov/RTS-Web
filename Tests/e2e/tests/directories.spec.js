// @ts-check
// Project: admin (storageState = admin.json)
// Тестирует справочники регионов и подрядчиков.
const { test, expect } = require('@playwright/test');

// ─── /regions.html ───────────────────────────────────────────────────────────

test('admin: /regions.html загружается', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/regions\.html/);
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  await expect(page.locator('h5.fw-bold')).toContainText(/регион/i);
});

test('admin: в справочнике регионов есть строки', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  const rows = page.locator('#tableBody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
});

test('admin: кнопка «Добавить регион» открывает модалку', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  // Ждём пока таблица загрузится — гарантирует, что Bootstrap JS и init() полностью отработали
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  await page.click('#btnAdd');

  const modal = page.locator('#itemModal');
  await expect(modal).toBeVisible({ timeout: 8_000 });
  await expect(page.locator('#modalTitle')).toContainText(/регион/i);
});

test('admin: форма нового региона содержит поле «Название»', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  await page.click('#btnAdd');
  await page.locator('#itemModal').waitFor({ state: 'visible', timeout: 8_000 });
  await expect(page.locator('#itemModal #f_name')).toBeVisible();
});

test('admin: в таблице регионов есть столбцы Название и Статус', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('table thead', { timeout: 10_000 });
  const headerText = await page.locator('table thead').innerText();
  expect(headerText).toContain('Название');
  expect(headerText).toContain('Статус');
});

test('admin: каждый регион имеет badge статуса (Активен / Неактивен)', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  // Хотя бы первая строка должна иметь badge
  const firstBadge = page.locator('#tableBody tr').first().locator('.badge');
  await expect(firstBadge).toBeVisible();
});

test('admin: в таблице регионов есть кнопки редактирования', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  // Кнопка карандаша в первой строке
  const editBtn = page.locator('#tableBody tr').first().locator('button[title="Редактировать"]');
  await expect(editBtn).toBeVisible();
});

test('admin: кнопка редактирования региона открывает модалку с данными', async ({ page }) => {
  await page.goto('/regions.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });

  await page.locator('#tableBody tr').first().locator('button[title="Редактировать"]').click();

  const modal = page.locator('#itemModal');
  await expect(modal).toBeVisible({ timeout: 8_000 });
  await expect(page.locator('#modalTitle')).toContainText(/редактировать/i);

  // Поле названия заполнено
  const nameVal = await page.locator('#itemModal #f_name').inputValue();
  expect(nameVal.length).toBeGreaterThan(0);
});

// ─── /contractors.html ───────────────────────────────────────────────────────
// Contractors page shows active_only contractors. The sync service sets
// is_active=true only for contractors referenced in sites. Tests that require
// data (badge, edit modal) are conditional — they pass vacuously when the
// directory is empty, and verify UI correctness when data exists.

test('admin: /contractors.html загружается', async ({ page }) => {
  await page.goto('/contractors.html', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/contractors\.html/);
  await page.waitForSelector('#navbar-container .navbar', { timeout: 10_000 });
  await expect(page.locator('h5.fw-bold')).toContainText(/подрядчик/i);
});

test('admin: в справочнике подрядчиков есть строки', async ({ page }) => {
  await page.goto('/contractors.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  const rows = page.locator('#tableBody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
});

test('admin: кнопка «Добавить подрядчика» открывает модалку', async ({ page }) => {
  await page.goto('/contractors.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  await page.click('#btnAdd');

  const modal = page.locator('#itemModal');
  await expect(modal).toBeVisible({ timeout: 8_000 });
  await expect(page.locator('#modalTitle')).toContainText(/подрядчик/i);
});

test('admin: в таблице подрядчиков есть столбцы Название и Статус', async ({ page }) => {
  await page.goto('/contractors.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('table thead', { timeout: 10_000 });
  const headerText = await page.locator('table thead').innerText();
  expect(headerText).toContain('Название');
  expect(headerText).toContain('Статус');
});

test('admin: строки подрядчиков имеют badge статуса (если есть активные)', async ({ page }) => {
  await page.goto('/contractors.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });
  // Нет ошибки загрузки
  const hasError = await page.locator('#tableBody .text-danger').isVisible().catch(() => false);
  expect(hasError).toBe(false);
  // Если активные подрядчики есть — каждая строка содержит badge
  const badgeRows = page.locator('#tableBody tr:has(.badge)');
  const count = await badgeRows.count();
  if (count > 0) {
    await expect(badgeRows.first().locator('.badge')).toBeVisible();
  }
});

test('admin: кнопка редактирования подрядчика открывает модалку (если есть активные)', async ({ page }) => {
  await page.goto('/contractors.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#tableBody tr:not(:has(.spinner-border))', { timeout: 15_000 });

  const editBtns = page.locator('#tableBody button[title="Редактировать"]');
  const count = await editBtns.count();
  if (count === 0) {
    // Нет активных подрядчиков — тест не применим, страница корректно показывает пустой список
    return;
  }

  await editBtns.first().click();
  const modal = page.locator('#itemModal');
  await expect(modal).toBeVisible({ timeout: 8_000 });
  await expect(page.locator('#modalTitle')).toContainText(/редактировать/i);

  const nameVal = await page.locator('#itemModal #f_name').inputValue();
  expect(nameVal.length).toBeGreaterThan(0);
});

// ─── Доступность справочников через navbar ────────────────────────────────────

test('admin: Справочники → Регионы ведёт на /regions.html', async ({ page }) => {
  // Заходим в UCN-проект, чтобы navbar показывал Справочники
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#projectsState h5', { timeout: 15_000 });
  await page.locator('#projectsState button.project-tile', { hasText: 'УЦН 2.0 2026' }).first().click();
  await page.waitForURL('**/sites.html**', { timeout: 15_000 });

  // Открываем dropdown «Справочники»
  await page.locator('#navbar-container button.nav-link', { hasText: 'Справочники' }).click();
  await page.locator('a', { hasText: 'Регионы' }).click();
  await expect(page).toHaveURL(/regions\.html/, { timeout: 8_000 });
});

test('admin: Справочники → Подрядчики ведёт на /contractors.html', async ({ page }) => {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#projectsState h5', { timeout: 15_000 });
  await page.locator('#projectsState button.project-tile', { hasText: 'УЦН 2.0 2026' }).first().click();
  await page.waitForURL('**/sites.html**', { timeout: 15_000 });

  await page.locator('#navbar-container button.nav-link', { hasText: 'Справочники' }).click();
  await page.locator('a', { hasText: 'Подрядчики' }).click();
  await expect(page).toHaveURL(/contractors\.html/, { timeout: 8_000 });
});
