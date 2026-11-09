import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, Clipboard, Clock3, FileText, Plus, Save, ShieldCheck, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button, Card, EmptyState, ErrorState, StatusPill } from "../../components/ui";
import { api, getApiError } from "../../lib/api";
import { compactId, formatCurrency, formatDate } from "../../lib/utils";
import type { Dispute, DisputeDraftRequest, DisputePage, DisputeUpdateRequest, Transaction, TransactionPage } from "../../types/api";

const reasons = [
  "FRAUDULENT_TRANSACTION", "DUPLICATE_CHARGE", "PRODUCT_NOT_RECEIVED",
  "SERVICE_NOT_PROVIDED", "INCORRECT_AMOUNT", "REFUND_NOT_RECEIVED", "OTHER",
] as const;

function ConfirmDialog({ title, message, confirmLabel, busy, onConfirm, onCancel }: { title: string; message: string; confirmLabel: string; busy: boolean; onConfirm: () => void; onCancel: () => void }) {
  const confirmButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmButton.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [busy, onCancel]);

  return <div className="dialog-backdrop" role="presentation"><div className="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dialog-title" aria-describedby="dialog-description"><h3 id="dialog-title">{title}</h3><p id="dialog-description">{message}</p><div className="dialog-actions"><Button className="button-secondary" onClick={onCancel} disabled={busy}>Go back</Button><Button ref={confirmButton} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</Button></div></div></div>;
}

function DraftForm({ onCreated }: { onCreated: (dispute: Dispute) => void }) {
  const [transactionId, setTransactionId] = useState("");
  const [claim, setClaim] = useState("");
  const transactions = useQuery({ queryKey: ["transactions", "dispute-draft"], queryFn: async () => (await api.get<TransactionPage>("/transactions?page=1&page_size=100")).data });
  const mutation = useMutation({ mutationFn: async (payload: DisputeDraftRequest) => (await api.post<Dispute>("/disputes/drafts", payload)).data, onSuccess: onCreated });
  return <Card className="draft-form"><div className="section-heading"><div><span className="eyebrow">New dispute</span><h3>Prepare a draft for review</h3></div><Plus size={19} /></div><p className="muted">The assistant prepares a draft only. You must review and explicitly confirm it before it is recorded as submitted.</p><form onSubmit={(event) => { event.preventDefault(); if (transactionId && claim.trim()) mutation.mutate({ transaction_id: transactionId, user_claim: claim.trim() }); }}><label>Transaction<select value={transactionId} onChange={(event) => setTransactionId(event.target.value)} required><option value="">Select a transaction</option>{transactions.data?.items.map((transaction) => <option value={transaction.id} key={transaction.id}>{transaction.merchant} · {compactId(transaction.id)}</option>)}</select></label><label>Your claim<textarea value={claim} onChange={(event) => setClaim(event.target.value)} minLength={1} maxLength={4000} required placeholder="Describe what happened in your own words." /></label>{transactions.isError && <div className="form-error">{getApiError(transactions.error)}</div>}{mutation.isError && <div className="form-error" role="alert">{getApiError(mutation.error, "Draft creation failed.")}</div>}<Button type="submit" disabled={!transactionId || !claim.trim() || mutation.isPending}>{mutation.isPending ? "Preparing draft…" : "Create draft"}</Button></form></Card>;
}

type EvidenceReference = { document_id?: string; document_title?: string; page_number?: number | null; chunk_index?: number };
type PolicyCitation = { document_id?: string; document_title?: string; page_number?: number | null; chunk_index?: number; content?: string };
type ParsedEvidence = {
  userClaim: string | null;
  explanation: string | null;
  transactionFacts: Record<string, string>;
  checklist: string[];
  missingInformation: string[];
  evidenceSupport: string | null;
  recommendedActions: string[];
  evidenceReferences: EvidenceReference[];
  policyCitations: PolicyCitation[];
};

function readEvidence(value: Record<string, unknown> | null): ParsedEvidence {
  const source = value ?? {};
  const list = (key: string) => Array.isArray(source[key]) ? source[key].filter((item): item is string => typeof item === "string") : [];
  const objects = (key: string) => Array.isArray(source[key]) ? source[key].filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
  const facts = source.transaction_facts && typeof source.transaction_facts === "object" ? source.transaction_facts as Record<string, unknown> : {};
  return {
    userClaim: typeof source.user_claim === "string" ? source.user_claim : null,
    explanation: typeof source.explanation === "string" ? source.explanation : null,
    transactionFacts: Object.fromEntries(Object.entries(facts).filter(([, item]) => typeof item === "string").map(([key, item]) => [key, item as string])),
    checklist: list("checklist"),
    missingInformation: list("missing_information"),
    evidenceSupport: typeof source.evidence_support === "string" ? source.evidence_support : null,
    recommendedActions: list("recommended_actions"),
    evidenceReferences: objects("evidence_references"),
    policyCitations: objects("policy_citations"),
  };
}

function DisputeHeader({ dispute }: { dispute: Dispute }) {
  const [copied, setCopied] = useState(false);
  async function copyId() {
    await navigator.clipboard?.writeText(dispute.id);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return <div className="dispute-header">
    <div><span className="eyebrow">Dispute review</span><h2>{dispute.title}</h2><p className="muted">Review the case details and next actions before making a decision.</p></div>
    <div className="dispute-header-meta"><StatusPill status={dispute.status} /><button className="copy-id" onClick={() => void copyId()} title="Copy dispute ID"><Clipboard size={14} /> {copied ? "Copied" : compactId(dispute.id)}</button><span className="date-meta">Created {formatDate(dispute.created_at)} · Updated {formatDate(dispute.updated_at)}</span></div>
  </div>;
}

function TransactionSummaryCard({ transaction, transactionId, facts }: { transaction?: Transaction; transactionId: string; facts: Record<string, string> }) {
  const amount = transaction ? formatCurrency(transaction.amount, transaction.currency) : facts.amount && facts.currency ? formatCurrency(facts.amount, facts.currency) : "Unavailable";
  return <Card><div className="section-heading"><div><span className="eyebrow">Payment context</span><h3>Transaction summary</h3></div><FileText size={19} /></div><div className="summary-hero"><strong>{amount}</strong><span>Transaction amount</span></div><div className="metadata-grid"><Meta label="Merchant" value={transaction?.merchant ?? facts.merchant ?? "Unavailable"} /><Meta label="Status" value={transaction?.status ?? facts.status ?? "Unavailable"} /><Meta label="Failure code" value={transaction?.failure_code ?? facts.failure_code ?? "Not recorded"} /><Meta label="Transaction ID" value={compactId(transaction?.id ?? transactionId)} /><Meta label="Transaction date" value={transaction?.occurred_at ? formatDate(transaction.occurred_at) : facts.occurred_at ? formatDate(facts.occurred_at) : "Unavailable"} /></div></Card>;
}

function Meta({ label, value }: { label: string; value: string }) {
  return <div className="metadata-item"><small>{label}</small><strong>{value.replaceAll("_", " ")}</strong></div>;
}

function DisputeDescriptionCard({ description, claim, explanation, facts, resolution }: { description: string; claim: string | null; explanation: string | null; facts: Record<string, string>; resolution: string | null }) {
  return <Card><div className="section-heading"><div><span className="eyebrow">Case narrative</span><h3>What happened?</h3></div><AlertCircle size={19} /></div><div className="narrative-stack"><div><small>Dispute description</small><p>{description}</p></div>{claim && <div><small>Customer's original claim</small><p>{claim}</p></div>}{explanation && <div><small>AI-generated explanation</small><p>{explanation}</p></div>}{Object.keys(facts).length > 0 && <div><small>Important transaction facts</small><div className="fact-list">{Object.entries(facts).filter(([key]) => !["transaction_id", "amount", "currency", "status", "merchant", "failure_code", "occurred_at"].includes(key)).map(([key, value]) => <span key={key}><b>{key.replaceAll("_", " ")}</b>{value}</span>)}</div></div>}{resolution && <div><small>Resolution</small><p>{resolution}</p></div>}</div></Card>;
}

function EvidenceVerificationCard({ evidence }: { evidence: ParsedEvidence }) {
  const state = evidence.evidenceSupport?.toLowerCase() ?? "unknown";
  const tone = state === "supported" ? "verified" : state === "insufficient_evidence" ? "failed" : state === "partially_supported" ? "missing" : "unknown";
  return <Card><div className="section-heading"><div><span className="eyebrow">Verification</span><h3>Evidence and verification</h3></div><ShieldCheck size={19} /></div><div className={`verification-banner ${tone}`}><CheckCircle2 size={17} /><div><strong>{evidence.evidenceSupport ? evidence.evidenceSupport.replaceAll("_", " ") : "Verification status unavailable"}</strong><span>Informational status from the dispute draft; no user verification action is available.</span></div></div><div className="checklist-list">{evidence.checklist.length ? evidence.checklist.map((item) => <div className="checklist-item" key={item}><Clock3 size={15} /><span>{item}</span></div>) : <EmptyState title="No verification checklist" description="No checklist items were provided for this draft." />}</div>{evidence.missingInformation.length > 0 && <div className="missing-list"><small>Missing information</small>{evidence.missingInformation.map((item) => <div key={item}><AlertCircle size={14} />{item}</div>)}</div>}</Card>;
}

function RecommendedActionsCard({ actions }: { actions: string[] }) {
  return <Card><div className="section-heading"><div><span className="eyebrow">Guidance</span><h3>Recommended next steps</h3></div></div>{actions.length ? <ol className="recommendation-list">{actions.map((action) => <li key={action}>{action}</li>)}</ol> : <EmptyState title="No recommendations available" description="Review the transaction and evidence above before taking action." />}</Card>;
}

function PolicyCitationsCard({ citations, references }: { citations: PolicyCitation[]; references: EvidenceReference[] }) {
  return <Card><div className="section-heading"><div><span className="eyebrow">Supporting sources</span><h3>Policy citations and references</h3></div></div>{citations.length || references.length ? <div className="citation-list">{citations.map((item, index) => <CitationItem item={item} index={index} key={`citation-${item.document_id ?? index}`} />)}{references.map((item, index) => <CitationItem item={item} index={index} key={`reference-${item.document_id ?? index}`} />)}</div> : <EmptyState title="No citations available" description="This draft does not contain policy citations or evidence references." />}</Card>;
}

function CitationItem({ item, index }: { item: PolicyCitation | EvidenceReference; index: number }) {
  const citation = "content" in item ? item.content : undefined;
  return <div className="citation-item"><FileText size={15} /><div><strong>{item.document_title ?? "Policy reference"}</strong><span>{item.page_number ? `Page ${item.page_number}` : `Reference ${index + 1}`}{citation ? ` · ${citation}` : ""}</span></div></div>;
}

function DisputeActionsPanel({ dispute, onEdit, onConfirm, onCancel }: { dispute: Dispute; onEdit: () => void; onConfirm: () => void; onCancel: () => void }) {
  const canEdit = dispute.status === "DRAFT";
  const canCancel = ["DRAFT", "SUBMITTED"].includes(dispute.status);
  return <Card className="actions-panel"><div className="section-heading"><div><span className="eyebrow">Case controls</span><h3>Manage dispute</h3></div></div><div className="lifecycle-summary"><StatusPill status={dispute.status} /><span>{canEdit ? "Draft requires your review." : "Lifecycle state is managed by PayFlow Copilot."}</span></div>{canEdit && <><Button className="button-secondary" onClick={onEdit}><Save size={15} /> Edit draft</Button><Button onClick={onConfirm}>Confirm submission</Button></>}{canCancel && <Button className="danger-button" onClick={onCancel}><X size={15} /> Cancel dispute</Button>}</Card>;
}

export function DisputesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [showForm, setShowForm] = useState(false);
  const disputes = useQuery({ queryKey: ["disputes", { page }], queryFn: async () => (await api.get<DisputePage>("/disputes", { params: { page, page_size: 20 } })).data });
  const items = disputes.data?.items.filter((item) => !status || item.status === status) ?? [];
  return <div className="page-stack"><div className="welcome"><div><span className="eyebrow">Case management</span><h2>Disputes</h2><p className="muted">Review payment issues and manage drafts that require your confirmation.</p></div><Button onClick={() => setShowForm((value) => !value)}><Plus size={16} /> {showForm ? "Hide draft form" : "New dispute draft"}</Button></div>{showForm && <DraftForm onCreated={(dispute) => { setShowForm(false); void queryClient.invalidateQueries({ queryKey: ["disputes"] }); navigate(`/disputes/${dispute.id}`); }} />}{disputes.isError ? <ErrorState message={getApiError(disputes.error)} onRetry={() => void disputes.refetch()} /> : <Card><div className="filter-bar"><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter disputes by status"><option value="">All statuses</option>{["DRAFT", "SUBMITTED", "UNDER_REVIEW", "RESOLVED", "REJECTED", "CANCELLED"].map((value) => <option value={value} key={value}>{value.replaceAll("_", " ")}</option>)}</select></div>{disputes.isLoading ? <div className="loading-lines"><span /><span /><span /></div> : items.length ? <><div className="table-wrap"><table><thead><tr><th>Dispute</th><th>Transaction</th><th>Reason</th><th>Status</th><th>Created</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><strong>{item.title}</strong><small>{compactId(item.id)}</small></td><td>{compactId(item.transaction_id)}</td><td>{item.reason.replaceAll("_", " ")}</td><td><StatusPill status={item.status} /></td><td>{formatDate(item.created_at)}</td><td><Link to={`/disputes/${item.id}`}>Review</Link></td></tr>)}</tbody></table></div><div className="pagination"><span>Page {disputes.data?.page} · {disputes.data?.total} total</span><div><Button className="button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ArrowLeft size={15} /></Button><Button className="button-secondary" disabled={(disputes.data?.items.length ?? 0) < 20} onClick={() => setPage((value) => value + 1)}><ArrowRight size={15} /></Button></div></div></> : <EmptyState title="No disputes found" description={status ? "No disputes match this status on the current page." : "Create a draft when you need to document a payment issue."} />}</Card>}</div>;
}

export function DisputeDetailPage() {
  const { disputeId } = useParams();
  const queryClient = useQueryClient();
  const dispute = useQuery({ queryKey: ["dispute", disputeId], enabled: Boolean(disputeId), queryFn: async () => (await api.get<Dispute>(`/disputes/${disputeId}`)).data });
  const transaction = useQuery({ queryKey: ["transaction", dispute.data?.transaction_id], enabled: Boolean(dispute.data?.transaction_id), queryFn: async () => (await api.get<Transaction>(`/transactions/${dispute.data?.transaction_id}`)).data });
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState<"confirm" | "cancel">();
  const actionLock = useRef(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [reason, setReason] = useState<Dispute["reason"]>("OTHER");
  const item = dispute.data;
  const update = useMutation({ mutationFn: async (payload: DisputeUpdateRequest) => (await api.patch<Dispute>(`/disputes/${disputeId}`, payload)).data, onSuccess: (value) => { queryClient.setQueryData(["dispute", disputeId], value); void queryClient.invalidateQueries({ queryKey: ["disputes"] }); setEditing(false); } });
  const lifecycle = useMutation({ mutationFn: async (action: "confirm" | "cancel") => (await api.post<Dispute>(`/disputes/${disputeId}/${action}`)).data, onSuccess: (value) => { actionLock.current = false; queryClient.setQueryData(["dispute", disputeId], value); void queryClient.invalidateQueries({ queryKey: ["disputes"] }); setConfirming(undefined); }, onError: () => { actionLock.current = false; } });
  if (dispute.isError) return <ErrorState message={getApiError(dispute.error)} onRetry={() => void dispute.refetch()} />;
  if (dispute.isLoading || !item) return <div className="loading-lines"><span /><span /><span /></div>;
  const current = item;
  function beginEdit() { setTitle(current.title); setDescription(current.description); setReason(current.reason); setEditing(true); }
  function submitLifecycle() { if (actionLock.current || !confirming) return; actionLock.current = true; lifecycle.mutate(confirming); }
  const evidence = readEvidence(item.evidence);
  return <div className="page-stack dispute-detail-page">
    <Link to="/disputes" className="back-link"><ArrowLeft size={15} /> Back to disputes</Link>
    <DisputeHeader dispute={item} />
    <div className="dispute-detail-layout">
      <main className="dispute-detail-main">
        <TransactionSummaryCard transaction={transaction.data} transactionId={item.transaction_id} facts={evidence.transactionFacts} />
        <DisputeDescriptionCard description={item.description} claim={evidence.userClaim} explanation={evidence.explanation} facts={evidence.transactionFacts} resolution={item.resolution} />
        <EvidenceVerificationCard evidence={evidence} />
        <RecommendedActionsCard actions={evidence.recommendedActions} />
        <PolicyCitationsCard citations={evidence.policyCitations} references={evidence.evidenceReferences} />
      </main>
      <aside className="dispute-detail-sidebar">
        <DisputeActionsPanel dispute={item} onEdit={beginEdit} onConfirm={() => setConfirming("confirm")} onCancel={() => setConfirming("cancel")} />
        {lifecycle.isError && <div className="form-error" role="alert">{getApiError(lifecycle.error, "Unable to update this dispute.")}</div>}
        {transaction.isError && <div className="form-error">Transaction details are unavailable. The dispute remains accessible.</div>}
      </aside>
    </div>
    {editing && <Card><div className="section-heading"><h3>Edit draft</h3><Button className="icon-button" aria-label="Close editor" onClick={() => setEditing(false)}><X size={17} /></Button></div><form onSubmit={(event) => { event.preventDefault(); update.mutate({ title, description, reason }); }}><label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={255} /></label><label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} required maxLength={12000} /></label><label>Reason<select value={reason} onChange={(event) => setReason(event.target.value as Dispute["reason"])}>{reasons.map((value) => <option value={value} key={value}>{value.replaceAll("_", " ")}</option>)}</select></label>{update.isError && <div className="form-error">{getApiError(update.error)}</div>}<Button type="submit" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save changes"}</Button></form></Card>}
    {confirming && <ConfirmDialog title={confirming === "confirm" ? "Confirm dispute submission?" : "Cancel this dispute?"} message={confirming === "confirm" ? "This records the dispute as submitted internally in PayFlow Copilot. It does not submit anything to a bank, card network, or external processor." : "This will cancel the dispute in PayFlow Copilot. This action cannot be undone through this screen."} confirmLabel={confirming === "confirm" ? "Confirm submission" : "Cancel dispute"} busy={lifecycle.isPending} onCancel={() => setConfirming(undefined)} onConfirm={submitLifecycle} />}
  </div>;
}
