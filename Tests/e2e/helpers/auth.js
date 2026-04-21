/**
 * login() — used ONLY in auth.spec.js which tests the actual login form.
 * All other test files use storageState from globalSetup and should
 * call navigateTo() instead of login().
 */
async function login(page, username, password) {
  await page.goto('/login.html');
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('#loginBtn');
  await page.waitForURL('**/index.html', { timeout: 45_000 });
}

/**
 * logout() — clicks Выйти in the user dropdown.
 * Toggle id = navbarUserToggle (from utils.js renderNavbar).
 */
async function logout(page) {
  const toggle = page.locator('#navbarUserToggle');
  await toggle.waitFor({ state: 'visible', timeout: 10_000 });
  await toggle.click();
  await page.locator('a:has-text("Выйти")').click();
  await page.waitForURL('**/login.html', { timeout: 10_000 });
}

/**
 * openUcnProject() — from /index.html click the UCN project tile.
 * Requires the page to already be authenticated (storageState loaded).
 */
async function openUcnProject(page) {
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#projectsState h5', { timeout: 15_000 });
  const ucnBtn = page.locator('#projectsState button.project-tile', { hasText: 'УЦН 2.0 2026' }).first();
  await ucnBtn.click();
  await page.waitForURL('**/sites.html**', { timeout: 15_000 });
}

module.exports = { login, logout, openUcnProject };
