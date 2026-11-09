import { expect, test } from "@playwright/test";

test("login, load dashboard, logout, and protect the dashboard", async ({ page }) => {
  let authenticated = false;
  await page.route("**/api/v1/auth/login", async (route) => {
    authenticated = true;
    await route.fulfill({ json: { access_token: "session-token", token_type: "bearer" } });
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    if (!authenticated) {
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Could not validate credentials" }) });
      return;
    }
    await route.fulfill({ json: { id: "user-1", email: "e2e@example.test", is_active: true, created_at: "2026-01-01T00:00:00Z" } });
  });
  await page.route("**/api/v1/transactions?*", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 5, pages: 0 } });
  });
  await page.route("**/api/v1/disputes?*", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 5 } });
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill("e2e@example.test");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /Good morning/ })).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});
