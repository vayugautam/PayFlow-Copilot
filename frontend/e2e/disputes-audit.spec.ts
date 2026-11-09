import { expect, test } from "@playwright/test";

test("dispute confirmation dialog requires explicit action", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("payflow_access_token", "test-token"));
  await page.route("**/auth/me", async (route) => route.fulfill({ json: { id: "user-1", email: "e2e@example.test", is_active: true, created_at: "2026-01-01T00:00:00Z" } }));
  await page.route("**/api/v1/disputes/dispute-1", async (route) => route.fulfill({ json: { id: "dispute-1", user_id: "user-1", transaction_id: "tx-1", conversation_id: null, title: "E2E draft", description: "Synthetic draft", reason: "OTHER", status: "DRAFT", evidence: {}, resolution: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", confirmed_at: null, resolved_at: null } }));
  await page.goto("/disputes/dispute-1");
  await page.getByRole("button", { name: "Confirm submission" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("does not submit anything to a bank");
});
