import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Search } from "lucide-react";
import { Button, Card, EmptyState, ErrorState } from "../../components/ui";
import { api, getApiError } from "../../lib/api";
import { compactId, formatDate } from "../../lib/utils";
import type { AuditLogPage as AuditPage } from "../../types/api";

export function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [action, setAction] = useState("");
  const logs = useQuery({ queryKey: ["audit-logs", { page, entityType, entityId, action }], queryFn: async () => (await api.get<AuditPage>("/audit-logs", { params: { page, page_size: 20, entity_type: entityType || undefined, entity_id: entityId || undefined, action: action || undefined } })).data });
  return <div className="page-stack"><div className="welcome"><div><span className="eyebrow">Immutable history</span><h2>Audit Logs</h2><p className="muted">Review activity recorded for your PayFlow Copilot workspace.</p></div></div><Card><div className="audit-filters"><label>Entity type<input value={entityType} onChange={(event) => { setEntityType(event.target.value); setPage(1); }} placeholder="dispute" /></label><label>Entity ID<div className="search-field"><Search size={15} /><input value={entityId} onChange={(event) => { setEntityId(event.target.value); setPage(1); }} placeholder="UUID" /></div></label><label>Action<input value={action} onChange={(event) => { setAction(event.target.value); setPage(1); }} placeholder="DISPUTE_CONFIRMED" /></label></div>{logs.isError ? <ErrorState message={getApiError(logs.error)} onRetry={() => void logs.refetch()} /> : logs.isLoading ? <div className="loading-lines"><span /><span /><span /></div> : logs.data?.items.length ? <><div className="table-wrap"><table><thead><tr><th>Action</th><th>Entity</th><th>Entity ID</th><th>Details</th><th>Recorded</th></tr></thead><tbody>{logs.data.items.map((log) => <tr key={log.id}><td><strong>{log.action}</strong></td><td>{log.entity_type}</td><td>{compactId(log.entity_id)}</td><td><details><summary>View</summary><pre>{JSON.stringify(log.details ?? {}, null, 2)}</pre></details></td><td>{formatDate(log.created_at)}</td></tr>)}</tbody></table></div><div className="pagination"><span>Page {logs.data.page} · {logs.data.total} total</span><div><Button className="button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ArrowLeft size={15} /></Button><Button className="button-secondary" disabled={logs.data.items.length < 20} onClick={() => setPage((value) => value + 1)}><ArrowRight size={15} /></Button></div></div></> : <EmptyState title="No audit events" description="Recorded activity will appear here." />}</Card></div>;
}
