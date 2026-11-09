import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BarChart3, Search } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Button, Card, EmptyState, ErrorState, StatusPill } from "../../components/ui";
import { api, getApiError } from "../../lib/api";
import { compactId, formatCurrency, formatDate } from "../../lib/utils";
import type { Transaction, TransactionAnalysis, TransactionPage } from "../../types/api";

export function TransactionsPage() {
  const [search, setSearch] = useState("");
  const [merchant, setMerchant] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => { const timer = window.setTimeout(() => { setMerchant(search); setPage(1); }, 300); return () => window.clearTimeout(timer); }, [search]);
  const transactions = useQuery({ queryKey: ["transactions", { merchant, status, page }], queryFn: async () => (await api.get<TransactionPage>("/transactions", { params: { page, page_size: 10, merchant: merchant || undefined, status: status || undefined } })).data });
  return <div className="page-stack"><div className="welcome"><div><span className="eyebrow">Payments</span><h2>Transactions</h2><p className="muted">Search and review your payment activity.</p></div></div><Card><div className="filter-bar"><label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search merchant" aria-label="Search merchant" /></label><select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Filter by status"><option value="">All statuses</option><option value="successful">Successful</option><option value="failed">Failed</option><option value="pending">Pending</option><option value="refunded">Refunded</option></select></div>{transactions.isError ? <ErrorState message={getApiError(transactions.error)} onRetry={() => void transactions.refetch()} /> : transactions.isLoading ? <div className="loading-lines"><span /><span /><span /><span /></div> : transactions.data?.items.length ? <><div className="table-wrap"><table><thead><tr><th>Transaction</th><th>Merchant</th><th>Amount</th><th>Status</th><th>Failure code</th><th>Date</th><th /></tr></thead><tbody>{transactions.data.items.map((transaction) => <tr key={transaction.id}><td><strong>{compactId(transaction.id)}</strong></td><td>{transaction.merchant}</td><td>{formatCurrency(transaction.amount, transaction.currency)}</td><td><StatusPill status={transaction.status} /></td><td>{transaction.failure_code || "—"}</td><td>{formatDate(transaction.occurred_at)}</td><td><Link to={`/transactions/${transaction.id}`}>View</Link></td></tr>)}</tbody></table></div><div className="pagination"><span>Page {transactions.data.page} of {transactions.data.pages || 1}</span><div><Button className="button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ArrowLeft size={15} /></Button><Button className="button-secondary" disabled={page >= transactions.data.pages} onClick={() => setPage((value) => value + 1)}><ArrowRight size={15} /></Button></div></div></> : <EmptyState title="No transactions found" description="Try adjusting your search or filters." />}</Card></div>;
}

function RetryLabel({ value }: { value: TransactionAnalysis["retry_eligibility"] }) {
  const labels = { retry_now: "Retry now", retry_after_action: "Retry after action", verify_status_first: "Verify status first", do_not_retry: "Do not retry", unknown: "Unknown" };
  return <span className={`retry-label ${value}`}>{labels[value]}</span>;
}

export function TransactionDetailPage() {
  const { transactionId } = useParams();
  const transaction = useQuery({ queryKey: ["transaction", transactionId], enabled: Boolean(transactionId), queryFn: async () => (await api.get<Transaction>(`/transactions/${transactionId}`)).data });
  const analysis = useQuery({ queryKey: ["transaction-analysis", transactionId], enabled: Boolean(transactionId), queryFn: async () => (await api.get<TransactionAnalysis>(`/transactions/${transactionId}/analysis`)).data });
  if (transaction.isError) return <ErrorState message={getApiError(transaction.error)} onRetry={() => void transaction.refetch()} />;
  if (transaction.isLoading || !transaction.data) return <div className="loading-lines"><span /><span /><span /></div>;
  const item = transaction.data;
  return <div className="page-stack"><Link to="/transactions" className="back-link"><ArrowLeft size={15} /> Back to transactions</Link><div className="welcome"><div><span className="eyebrow">Transaction detail</span><h2>{item.merchant}</h2><p className="muted">{item.id}</p></div><StatusPill status={item.status} /></div><div className="detail-grid"><Card><div className="detail-fields"><div><small>Amount</small><strong>{formatCurrency(item.amount, item.currency)}</strong></div><div><small>Payment method</small><strong>{item.payment_method || "—"}</strong></div><div><small>Failure code</small><strong>{item.failure_code || "—"}</strong></div><div><small>Failure details</small><strong>{item.failure_description || item.failure_reason || "—"}</strong></div><div><small>Occurred</small><strong>{formatDate(item.occurred_at)}</strong></div><div><small>Description</small><strong>{item.description || "—"}</strong></div></div></Card><Card><div className="section-heading"><div><span className="eyebrow">Deterministic analysis</span><h3>Payment intelligence</h3></div><BarChart3 size={19} /></div>{analysis.isLoading ? <div className="loading-lines"><span /><span /></div> : analysis.isError ? <ErrorState message={getApiError(analysis.error)} onRetry={() => void analysis.refetch()} /> : analysis.data && <div className="analysis-content"><div className="analysis-heading"><strong>{analysis.data.title}</strong><StatusPill status={analysis.data.severity} /></div><p>{analysis.data.explanation}</p><RetryLabel value={analysis.data.retry_eligibility} /><h4>Recommended next steps</h4><ul>{analysis.data.recommended_actions.map((action) => <li key={action}>{action}</li>)}</ul><Link className="button button-secondary" to={`/copilot?transactionId=${item.id}`}>Ask AI Copilot about this transaction</Link></div>}</Card></div></div>;
}
