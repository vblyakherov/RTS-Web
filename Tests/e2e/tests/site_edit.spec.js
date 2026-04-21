// @ts-check
// Project: admin (storageState = admin.json)
// Тестирует редактирование карточки объекта и историю изменений.
const { test, expect } = require('@playwright/test');
const { openUcnProject } = require('../helpers/auth');

// Открыть карточку первого объекта в списке
async function openFirstSite(page) {
  await openUcnProject(page);
  await page.waitForSelector('#sitesTableBody tr:not(:has(.spinner-border))', { timeout: 20_000 });
  const firstLink = page.locator('#sitesTableBody tr a').first();
  await firstLink.click();
  await page.waitForURL('**/site.html**', { timeout: 10_000 });
  // Ждём загрузку карточки (исчезновение спиннера)
  await page.waitForSelector('#loadingState.d-none, #siteContent', { timeout: 15_000 }).catch(() => {});
  await page.waitForSelector('#siteHeader h5', { timeout: 10_000 });
}

// ─── Просмотр карточки ───────────────────────────────────────────────────────

test('карточка объекта содержит ID объекта в шапке', async ({ page }) => {
  await openFirstSite(page);
  const header = page.locator('#siteHeader');
  await expect(header).toContainText(/UCN-2026-\d{4}/);
});

test('карточка объекта показывает статус-badge', async ({ page }) => {
  await openFirstSite(page);
  const badge = page.locator('#siteHeader .badge');
  await expect(badge).toBeVisible();
});

test('поле ID объекта заполнено и доступно только для чтения', async ({ page }) => {
  await openFirstSite(page);
  const siteIdEl = page.locator('#f_site_id');
  await expect(siteIdEl).toBeVisible();
  const text = await siteIdEl.innerText();
  expect(text).toMatch(/UCN-2026-\d{4}/);
});

test('изначально поля формы задизейблены (не режим редактирования)', async ({ page }) => {
  await openFirstSite(page);
  // До нажатия «Редактировать» поля должны быть disabled или readonly
  const nameInput = page.locator('#f_name');
  await expect(nameInput).toBeVisible();
  const isDisabled = await nameInput.isDisabled();
  expect(isDisabled).toBe(true);
});

// ─── Режим редактирования ────────────────────────────────────────────────────

test('кнопка «Редактировать» переводит в режим редактирования', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: 'Редактировать' }).click();

  // После клика поле должно стать активным
  const nameInput = page.locator('#f_name');
  await expect(nameInput).toBeEnabled({ timeout: 5_000 });
});

test('в режиме редактирования появляется кнопка «Сохранить»', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: 'Редактировать' }).click();

  const saveBtn = page.locator('button', { hasText: 'Сохранить' });
  await expect(saveBtn).toBeVisible({ timeout: 5_000 });
});

test('в режиме редактирования появляется кнопка «Отмена»', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: 'Редактировать' }).click();

  const cancelBtn = page.locator('#actionBar button', { hasText: 'Отмена' });
  await expect(cancelBtn).toBeVisible({ timeout: 5_000 });
});

test('кнопка «Отмена» выходит из режима редактирования', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: 'Редактировать' }).click();
  await expect(page.locator('#f_name')).toBeEnabled({ timeout: 5_000 });

  await page.locator('#actionBar button', { hasText: 'Отмена' }).click();

  // Поле снова должно стать disabled
  await expect(page.locator('#f_name')).toBeDisabled({ timeout: 5_000 });
});

test('изменение заметок и сохранение — страница перезагружается с тем же объектом', async ({ page }) => {
  await openFirstSite(page);

  // Запоминаем текущий URL
  const url = page.url();

  await page.locator('button', { hasText: 'Редактировать' }).click();
  await expect(page.locator('#f_notes')).toBeEnabled({ timeout: 5_000 });

  // Читаем текущее значение и дописываем пробел (безопасное изменение)
  const oldNotes = await page.locator('#f_notes').inputValue();
  const newNotes = oldNotes.trim() + ' ';
  await page.locator('#f_notes').fill(newNotes);

  await page.locator('button', { hasText: 'Сохранить' }).click();

  // После сохранения — controlled reload на ту же страницу
  await page.waitForURL(url, { timeout: 15_000 });
  await page.waitForSelector('#siteHeader h5', { timeout: 10_000 });

  // Карточка снова показывает ID объекта
  await expect(page.locator('#siteHeader')).toContainText(/UCN-2026-\d{4}/);
});

test('выбор статуса «Строительство» доступен в режиме редактирования', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: 'Редактировать' }).click();

  const statusSel = page.locator('#f_status');
  await expect(statusSel).toBeEnabled({ timeout: 5_000 });
  // Просто убеждаемся, что select содержит нужную опцию
  await expect(statusSel.locator('option[value="construction"]')).toHaveCount(1);
});

// ─── Кнопка «История» ────────────────────────────────────────────────────────

test('admin: кнопка «История» видна на карточке объекта', async ({ page }) => {
  await openFirstSite(page);
  const historyBtn = page.locator('button', { hasText: /история/i });
  await expect(historyBtn).toBeVisible({ timeout: 8_000 });
});

test('admin: кнопка «История» открывает модальное окно истории', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: /история/i }).click();

  const modal = page.locator('#historyModal');
  await expect(modal).toBeVisible({ timeout: 8_000 });
  await expect(modal).toContainText(/история изменений/i);
});

test('в модалке истории есть кнопка «Обновить»', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: /история/i }).click();
  await page.locator('#historyModal').waitFor({ state: 'visible', timeout: 8_000 });

  const refreshBtn = page.locator('#historyModal button', { hasText: 'Обновить' });
  await expect(refreshBtn).toBeVisible();
});

test('модалка истории загружается без ошибок', async ({ page }) => {
  await openFirstSite(page);
  await page.locator('button', { hasText: /история/i }).click();
  await page.locator('#historyModal').waitFor({ state: 'visible', timeout: 8_000 });

  // Ждём пока historyList станет видимым (d-none убирается после загрузки)
  await page.waitForFunction(
    () => !document.getElementById('historyList').classList.contains('d-none'),
    { timeout: 15_000 },
  );

  // Не должно быть видно alert-danger внутри модалки
  const errorAlert = page.locator('#historyModal .alert-danger');
  const hasError = await errorAlert.isVisible().catch(() => false);
  expect(hasError).toBe(false);
});
