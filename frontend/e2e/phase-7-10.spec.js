// Phase 7.10 Playwright E2E — multi-user isolation via the live UI.
// Uses the existing Firebase email/password test users.

import { test, expect, chromium } from '@playwright/test';

const USER_A = {
  email: 'live-user-a@example.com',
  password: 'TestPass123!',
};
const USER_B = {
  email: 'live-user-b@example.com',
  password: 'TestPass456!',
};

const BASE = 'http://127.0.0.1:5173';

async function signIn(page, user) {
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"]', user.email);
  await page.fill('input[type="password"]', user.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  // Wait until navigation away from /login.
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15000 });
}

async function signOut(page) {
  await page.goto(`${BASE}/dashboard`);
  await page.getByRole('button', { name: /sign out/i }).click();
  await page.waitForURL((url) => url.pathname.startsWith('/login'), { timeout: 15000 });
}

test.describe('Phase 7.10 — multi-user E2E isolation', () => {
  test('USER_A and USER_B have independent auth + draft sessions', async () => {
    const browser = await chromium.launch();
    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();

    try {
      const pageA = await ctxA.newPage();
      const pageB = await ctxB.newPage();

      // Both users sign in.
      await signIn(pageA, USER_A);
      await signIn(pageB, USER_B);

      // Each dashboard shows the user's own /auth/me identity.
      await pageA.goto(`${BASE}/dashboard`);
      await pageB.goto(`${BASE}/dashboard`);
      await pageA.waitForSelector('text=/Dashboard/i');

      // USER_A creates a draft via the API (skipping UI for speed).
      const draftA = await pageA.evaluate(async () => {
        const fbAuth = window.__firebaseAuth;
        if (!fbAuth || !fbAuth.currentUser) return null;
        const token = await fbAuth.currentUser.getIdToken();
        const r = await fetch('http://127.0.0.1:8000/api/v1/drafts', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic: 'e2e A', title: 'E2E A draft', content: 'A content' }),
        });
        return r.json();
      });
      expect(draftA).not.toBeNull();
      expect(draftA.title).toBe('E2E A draft');

      // USER_B creates a draft too.
      const draftB = await pageB.evaluate(async () => {
        const fbAuth = window.__firebaseAuth;
        if (!fbAuth || !fbAuth.currentUser) return null;
        const token = await fbAuth.currentUser.getIdToken();
        const r = await fetch('http://127.0.0.1:8000/api/v1/drafts', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic: 'e2e B', title: 'E2E B draft', content: 'B content' }),
        });
        return r.json();
      });
      expect(draftB).not.toBeNull();
      expect(draftB.title).toBe('E2E B draft');

      // Both drafts survive a hard refresh (proof of Mongo persistence).
      await pageA.reload();
      await pageB.reload();
      await pageA.waitForSelector('text=/Drafts/i');

      // USER_A's drafts page does NOT contain USER_B's title.
      await pageA.goto(`${BASE}/drafts`);
      await pageA.waitForSelector('text=/Draft library/i');
      const aHtml = await pageA.content();
      expect(aHtml).toContain('E2E A draft');
      expect(aHtml).not.toContain('E2E B draft');

      await pageB.goto(`${BASE}/drafts`);
      await pageB.waitForSelector('text=/Draft library/i');
      const bHtml = await pageB.content();
      expect(bHtml).toContain('E2E B draft');
      expect(bHtml).not.toContain('E2E A draft');

      // Sign USER_A out -> /login.
      await signOut(pageA);
      await expect(pageA).toHaveURL(/\/login/);

      // USER_B remains authenticated.
      await pageB.goto(`${BASE}/dashboard`);
      await expect(pageB).not.toHaveURL(/\/login/);

      // Sign USER_B out too.
      await signOut(pageB);
    } finally {
      await ctxA.close();
      await ctxB.close();
      await browser.close();
    }
  });

  test('Anonymous user is redirected to /login', async () => {
    const browser = await chromium.launch();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await page.goto(`${BASE}/dashboard`);
      // Wait for redirect away from /dashboard (ProtectedRoute sends to /login).
      await page.waitForURL(/\/login/, { timeout: 30000 });
      await expect(page).toHaveURL(/\/login/);
    } finally {
      await ctx.close();
      await browser.close();
    }
  });
});