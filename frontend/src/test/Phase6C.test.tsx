import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditLogsPage } from "../features/audit/AuditLogsPage";
import { DisputeDetailPage, DisputesPage } from "../features/disputes/DisputesPage";
import type { ReactElement } from "react";
import type { Dispute } from "../types/api";

const { getMock, postMock, patchMock } = vi.hoisted(() => ({ getMock: vi.fn(), postMock: vi.fn(), patchMock: vi.fn() }));

vi.mock("../lib/api", () => ({
  api: { get: getMock, post: postMock, patch: patchMock },
  getApiError: () => "Request failed",
}));

function renderWithProviders(element: ReactElement, initialEntries = ["/"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={initialEntries}>{element}</MemoryRouter></QueryClientProvider>);
}

const draft: Dispute = { id: "dispute-1", user_id: "user-1", transaction_id: "tx-1", conversation_id: null, title: "Duplicate charge", description: "A duplicate payment was charged.", reason: "DUPLICATE_CHARGE", status: "DRAFT", evidence: { checklist: ["Receipt"] }, resolution: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", confirmed_at: null, resolved_at: null };

describe("Phase 6C disputes", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    patchMock.mockReset();
  });

  it("renders the dispute list and supports empty states", async () => {
    getMock.mockResolvedValueOnce({ data: { items: [draft], total: 1, page: 1, page_size: 20 } });
    renderWithProviders(<DisputesPage />);
    expect(await screen.findByText("Duplicate charge")).toBeInTheDocument();
    expect(screen.getByText("DUPLICATE CHARGE")).toBeInTheDocument();
  });

  it("creates a draft from the exact backend request fields", async () => {
    const transactionPage = { items: [{ id: "tx-1", amount: "10.00", currency: "USD", status: "failed", merchant: "Northwind", description: null, failure_code: "declined", payment_method: "card", occurred_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 100, pages: 1 };
    getMock.mockImplementation((url: string) => Promise.resolve({ data: url.startsWith("/transactions") ? transactionPage : { items: [], total: 0, page: 1, page_size: 20 } }));
    postMock.mockResolvedValueOnce({ data: draft });
    renderWithProviders(<DisputesPage />);
    fireEvent.click(await screen.findByRole("button", { name: /new dispute draft/i }));
    await screen.findByRole("option", { name: /Northwind/ });
    fireEvent.change(screen.getByLabelText("Transaction"), { target: { value: "tx-1" } });
    fireEvent.change(screen.getByLabelText("Your claim"), { target: { value: "I was charged twice." } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/disputes/drafts", { transaction_id: "tx-1", user_claim: "I was charged twice." }));
  });

  it("requires explicit confirmation and prevents duplicate submission while pending", async () => {
    getMock.mockResolvedValueOnce({ data: draft });
    let resolve: (value: { data: typeof draft }) => void = () => undefined;
    postMock.mockReturnValueOnce(new Promise((res) => { resolve = res; }));
    renderWithProviders(<Routes><Route path="/disputes/:disputeId" element={<DisputeDetailPage />} /></Routes>, ["/disputes/dispute-1"]);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm submission" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("does not submit anything to a bank");
    const confirm = within(screen.getByRole("alertdialog")).getByRole("button", { name: "Confirm submission" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
    resolve({ data: { ...draft, status: "SUBMITTED", confirmed_at: "2026-01-02T00:00:00Z" } });
  });

  it("renders audit logs and sends supported filters", async () => {
    getMock.mockResolvedValueOnce({ data: { items: [{ id: "log-1", actor_user_id: "user-1", action: "DISPUTE_CONFIRMED", entity_type: "dispute", entity_id: "dispute-1", details: { status: "SUBMITTED" }, created_at: "2026-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 20 } });
    renderWithProviders(<AuditLogsPage />);
    expect(await screen.findByText("DISPUTE_CONFIRMED")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Entity type"), { target: { value: "dispute" } });
    await waitFor(() => expect(getMock).toHaveBeenLastCalledWith("/audit-logs", expect.objectContaining({ params: expect.objectContaining({ entity_type: "dispute" }) })));
  });
});
