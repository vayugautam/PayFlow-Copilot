import { expect, test } from "@playwright/test";

test("opens a transaction and renders deterministic failure analysis", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("payflow_access_token", "test-token"));
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({ json: { id: "user-1", email: "e2e@example.test", is_active: true, created_at: "2026-01-01T00:00:00Z" } });
  });
  await page.route("**/api/v1/transactions/tx-1", async (route) => {
    await route.fulfill({ json: { id: "tx-1", amount: "12.50", currency: "USD", status: "failed", merchant: "E2E Merchant", description: "Synthetic payment", failure_code: "declined", payment_method: "card", occurred_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" } });
  });
  await page.route("**/api/v1/transactions/tx-1/analysis", async (route) => {
    await route.fulfill({ json: { transaction_id: "tx-1", transaction_status: "failed", failure_code: "declined", category: "issuer_decline", title: "Payment declined", explanation: "The issuer declined the payment.", recommended_actions: ["Verify available balance."], retry_eligibility: "retry_after_action", severity: "medium" } });
  });

  await page.goto("/transactions/tx-1");
  await expect(page.getByRole("heading", { name: "E2E Merchant" })).toBeVisible();
  await expect(page.getByText("Payment declined")).toBeVisible();
  await expect(page.getByText("Verify available balance.")).toBeVisible();
  await expect(page.getByRole("link", { name: /Ask AI Copilot/ })).toHaveAttribute("href", "/copilot?transactionId=tx-1");
});
