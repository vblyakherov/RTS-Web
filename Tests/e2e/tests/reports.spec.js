// @ts-check
// Project: admin project (storageState = admin.json)
const { test, expect } = require('@playwright/test');
const { openUcnProject } = require('../helpers/auth');

async function openReports(page) {
  await page.locator('#navbar-container .nav-link', { hasText: 'Отчеты' }).click();
  await page.waitForURL('**/reports.html**', { timeout: 15_000 });
}

async function openPlaceholderProject(page, name = 'ТСПУ') {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#projectsState h5', { timeout: 15_000 });
  await page.locator('#projectsState button.project-tile', { hasText: name }).first().click();
  await page.waitForURL('**/project.html**', { timeout: 15_000 });
}

test('внутри проекта в navbar есть ссылка «Отчеты»', async ({ page }) => {
  await openUcnProject(page);
  await expect(page.locator('#navbar-container .nav-link', { hasText: 'Отчеты' })).toBeVisible();
});

test('UCN: страница отчетов загружается и показывает список отчетов', async ({ page }) => {
  await openUcnProject(page);
  await openReports(page);

  await expect(page.locator('#reportsCatalog')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#reportsCatalog [data-report-key]')).toHaveCount(2, { timeout: 15_000 });
  await expect(page.locator('#activeReportTitle')).toBeVisible({ timeout: 15_000 });
});

test('UCN: на странице отчетов есть кнопки выгрузки PDF, PPT и Excel', async ({ page }) => {
  await openUcnProject(page);
  await openReports(page);

  await expect(page.locator('#downloadPdfBtn')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#downloadPptBtn')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#downloadExcelBtn')).toBeVisible({ timeout: 15_000 });
});

test('placeholder: раздел отчетов открывается и показывает пустой state', async ({ page }) => {
  await openPlaceholderProject(page, 'ТСПУ');
  await openReports(page);

  await expect(page.locator('#reportsEmptyState')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#reportsEmptyState')).toContainText('пока не настроены');
});
