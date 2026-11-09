import { expect, test } from "@playwright/test";

test("transaction list renders backend-shaped data", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("payflow_access_token", "test-token"));
  await page.route("**/auth/me", async (route) => route.fulfill({ json: { id: "user-1", email: "e2e@example.test", is_active: true, created_at: "2026-01-01T00:00:00Z" } }));
  await page.route("**/transactions?*", async (route) => route.fulfill({ json: { items: [{ id: "tx-1", amount: "12.50", currency: "USD", status: "failed", merchant: "E2E Merchant", description: null, failure_code: "declined", payment_method: "card", occurred_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 10, pages: 1 } }));
  await page.goto("/transactions");
  await expect(page.getByText("E2E Merchant")).toBeVisible();
  await expect(page.getByText("declined")).toBeVisible();
});
