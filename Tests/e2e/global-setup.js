// @ts-check
/**
 * Global setup: log in as each test user ONCE and save browser storage state.
 * This avoids repeated bcrypt logins that block the Python event loop.
 */
const { chromium, request } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const USERS = [
  {
    username: requireEnv('E2E_ADMIN_USERNAME'),
    password: requireEnv('E2E_ADMIN_PASSWORD'),
    file: 'admin.json',
  },
  {
    username: requireEnv('E2E_USER_USERNAME'),
    password: requireEnv('E2E_USER_PASSWORD'),
    file: 'user.json',
  },
];

async function loginAndSave(username, password, stateFile) {
  const apiContext = await request.newContext();
  const res = await apiContext.post(`${BASE_URL}/api/v1/auth/login`, {
    data: { username, password },
    headers: { 'Content-Type': 'application/json' },
  });

  if (!res.ok()) {
    throw new Error(`Global setup: login failed for ${username}: ${res.status()} ${await res.text()}`);
  }

  const { access_token } = await res.json();
  await apiContext.dispose();

  // Launch browser, inject token, save storage state
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  await page.goto(`${BASE_URL}/login.html`, { waitUntil: 'domcontentloaded' });
  await page.evaluate((token) => {
    localStorage.setItem('token', token);
  }, access_token);

  await ctx.storageState({ path: stateFile });
  await browser.close();
  console.log(`  [global-setup] saved state for ${username} → ${stateFile}`);
}

module.exports = async function globalSetup() {
  const statesDir = path.join(__dirname, '.auth');
  if (!fs.existsSync(statesDir)) fs.mkdirSync(statesDir, { recursive: true });

  for (const u of USERS) {
    await loginAndSave(u.username, u.password, path.join(statesDir, u.file));
  }
};
