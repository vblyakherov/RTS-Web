// @ts-check
const { defineConfig, devices } = require('@playwright/test');
const path = require('path');

const ADMIN_STATE = path.join(__dirname, '.auth/admin.json');
const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  globalSetup: require.resolve('./global-setup.js'),

  use: {
    baseURL: BASE_URL,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    // Tests that need admin auth
    {
      name: 'admin',
      use: {
        ...devices['Desktop Chrome'],
        storageState: ADMIN_STATE,
      },
      testMatch: ['**/admin.spec.js', '**/projects.spec.js', '**/sites.spec.js', '**/site_edit.spec.js', '**/directories.spec.js'],
    },
    // Tests that use their own login (form tests, logout tests, role checks)
    {
      name: 'auth',
      use: { ...devices['Desktop Chrome'] },
      testMatch: ['**/auth.spec.js'],
    },
  ],
});
