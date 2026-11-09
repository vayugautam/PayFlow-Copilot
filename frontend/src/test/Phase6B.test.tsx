import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CopilotPage } from "../features/copilot/CopilotPage";
import { TransactionDetailPage, TransactionsPage } from "../features/transactions/TransactionsPage";

const { getMock, postMock } = vi.hoisted(() => ({ getMock: vi.fn(), postMock: vi.fn() }));

vi.mock("../lib/api", () => ({
  api: { get: getMock, post: postMock },
  getApiError: () => "Request failed",
}));

function renderWithProviders(element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);
}

describe("Phase 6B transaction views", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
  });

  it("renders filtered transaction results", async () => {
    getMock.mockResolvedValueOnce({ data: { items: [{ id: "tx-1", amount: "12.50", currency: "USD", status: "failed", merchant: "Northwind", description: null, failure_code: "declined", payment_method: "card", occurred_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 10, pages: 1 } });
    renderWithProviders(<TransactionsPage />);
    expect(await screen.findByText("Northwind")).toBeInTheDocument();
    expect(screen.getByText("declined")).toBeInTheDocument();
  });

  it("renders transaction analysis and retry eligibility", async () => {
    getMock.mockResolvedValueOnce({ data: { id: "tx-1", amount: "12.50", currency: "USD", status: "failed", merchant: "Northwind", description: null, failure_code: "declined", payment_method: "card", occurred_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" } });
    getMock.mockResolvedValueOnce({ data: { transaction_id: "tx-1", transaction_status: "failed", failure_code: "declined", category: "authorization", title: "Authorization failed", explanation: "The issuer declined the payment.", recommended_actions: ["Contact the issuer"], retry_eligibility: "do_not_retry", severity: "high" } });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/transactions/tx-1"]}><Routes><Route path="/transactions/:transactionId" element={<TransactionDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText("Authorization failed")).toBeInTheDocument();
    expect(screen.getByText("Do not retry")).toBeInTheDocument();
  });
});

describe("Phase 6B copilot", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
  });

  it("shows an empty conversation state", async () => {
    getMock.mockResolvedValueOnce({ data: [] });
    renderWithProviders(<CopilotPage />);
    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
  });

  it("sends a message and renders returned citation and tool metadata", async () => {
    getMock.mockImplementation((url: string) => Promise.resolve({ data: url.includes("/messages") ? [] : [{ id: "conversation-1", title: "Support", is_archived: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }] }));
    postMock.mockResolvedValueOnce({ data: { conversation_id: "conversation-1", user_message: { id: "user-1", role: "user", content: "Explain this", tool_name: null, created_at: "2026-01-01T00:00:00Z" }, assistant_message: { id: "assistant-1", role: "assistant", content: "**A grounded answer**", tool_name: null, created_at: "2026-01-01T00:00:00Z" }, citations: [{ document_id: "doc-1", document_title: "Refund policy", page_number: 2, chunk_index: 1, relevant_excerpt: "Refunds are available within 30 days." }], tool_executions: [{ tool_name: "retrieve_payment_policy", success: true }], created_at: "2026-01-01T00:00:00Z" } });
    renderWithProviders(<CopilotPage />);
    const composer = await screen.findByLabelText("Message");
    fireEvent.change(composer, { target: { value: "Explain this" } });
    fireEvent.submit(composer.closest("form")!);
    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/chat/conversations/conversation-1/messages", { content: "Explain this" }));
    expect(await screen.findByText("A grounded answer")).toBeInTheDocument();
    expect(await screen.findByText("Refund policy")).toBeInTheDocument();
    expect(screen.getByText(/Policy retrieval: complete/)).toBeInTheDocument();
  });
});
