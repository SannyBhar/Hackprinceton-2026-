import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./e2e',testMatch:'**/*.pw.ts',workers:1,
  use:{baseURL:'http://127.0.0.1:8011',headless:true,screenshot:'only-on-failure'},
  webServer:{command:'GRASSROOT_STORAGE=sqlite GRASSROOT_DATA_DIR=../work/e2e-data ../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --port 8011',url:'http://127.0.0.1:8011/api/state',reuseExistingServer:false},
});
