import { expect, test } from "@playwright/test";

test("creates a conversation, sends a message, and displays grounded response metadata", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("payflow_access_token", "test-token"));
  let conversationCreated = false;
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({ json: { id: "user-1", email: "e2e@example.test", is_active: true, created_at: "2026-01-01T00:00:00Z" } });
  });
  await page.route("**/api/v1/chat/conversations", async (route) => {
    if (route.request().method() === "POST") {
      conversationCreated = true;
      await route.fulfill({ status: 201, json: { id: "conversation-1", title: null, is_archived: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" } });
      return;
    }
    await route.fulfill({ json: conversationCreated ? [{ id: "conversation-1", title: "Payment support", is_archived: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }] : [] });
  });
  await page.route("**/api/v1/chat/conversations/conversation-1/messages", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        json: {
          conversation_id: "conversation-1",
          user_message: { id: "message-1", role: "user", content: "Explain my failed payment", tool_name: null, created_at: "2026-01-01T00:00:00Z" },
          assistant_message: { id: "message-2", role: "assistant", content: "**The payment was declined.**", tool_name: null, created_at: "2026-01-01T00:00:01Z" },
          citations: [{ document_id: "doc-1", document_title: "Refund policy", page_number: 1, chunk_index: 0, relevant_excerpt: "Refunds are reviewed within five days." }],
          tool_executions: [{ tool_name: "analyze_transaction_failure", success: true }],
          created_at: "2026-01-01T00:00:01Z",
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.goto("/copilot");
  await page.getByRole("button", { name: "New conversation" }).first().click();
  await expect(page.getByLabel("Message")).toBeVisible();
  await page.getByLabel("Message").fill("Explain my failed payment");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("The payment was declined.")).toBeVisible();
  await expect(page.getByText("Sources (1)")).toBeVisible();
  await expect(page.getByText("Transaction analysis: complete")).toBeVisible();
});
