import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, ChevronDown, Clipboard, FileText, Menu, Plus, Search, Send, Sparkles, Wrench, X, Zap } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { Button, Card, EmptyState, ErrorState } from "../../components/ui";
import { api, getApiError } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import type { ChatMessage, ChatMessageResponse, Citation, Conversation, ToolExecutionSummary } from "../../types/api";

type Suggestion = { title: string; example: string; prompt: string; icon: typeof Zap };
const suggestions: Suggestion[] = [
  { title: "Investigate a Transaction", example: "Investigate my latest failed payment.", prompt: "Investigate my latest failed payment.", icon: Search },
  { title: "Explain Payment Failure", example: "Why was my Razorpay payment declined?", prompt: "Why was my Razorpay payment declined?", icon: Zap },
  { title: "Payment Policy Questions", example: "What is the refund policy for failed payments?", prompt: "What is the refund policy for failed payments?", icon: FileText },
  { title: "Prepare a Dispute", example: "Help me prepare a dispute for a failed transaction.", prompt: "Help me prepare a dispute for a failed transaction.", icon: Wrench },
];

const toolLabels: Record<string, string> = {
  get_transaction: "Looking up transaction",
  list_transactions: "Retrieving payment history",
  analyze_transaction_failure: "Analyzing payment failure",
  retrieve_payment_policy: "Searching payment policies",
};

function MarkdownText({ content }: { content: string }) {
  return <div className="markdown-content">{content.split(/\n{2,}/).map((block, index) => {
    const lines = block.split("\n");
    const list = lines.every((line) => /^[-*]\s/.test(line));
    const inline = (value: string) => value.split(/(`[^`]+`|\*\*.+?\*\*)/g).map((part, partIndex) => {
      if (part.startsWith("`") && part.endsWith("`")) return <code key={partIndex}>{part.slice(1, -1)}</code>;
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={partIndex}>{part.slice(2, -2)}</strong>;
      return <span key={partIndex}>{part}</span>;
    });
    return list ? <ul key={index}>{lines.map((line) => <li key={line}>{inline(line.slice(2))}</li>)}</ul> : <p key={index}>{lines.map((line, lineIndex) => <span key={`${line}-${lineIndex}`}>{inline(line)}{lineIndex < lines.length - 1 && <br />}</span>)}</p>;
  })}</div>;
}

function ConversationHistory({ conversations, selected, search, onSearch, onSelect }: { conversations: Conversation[]; selected?: string; search: string; onSearch: (value: string) => void; onSelect: (id: string) => void }) {
  const filtered = conversations.filter((item) => (item.title || "Untitled conversation").toLowerCase().includes(search.toLowerCase()));
  const groups = groupConversations(filtered);
  return <div className="conversation-history"><label className="conversation-search"><Search size={15} /><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search conversations" aria-label="Search conversations" /></label>{Object.entries(groups).map(([label, items]) => items.length ? <div className="conversation-group" key={label}><span className="conversation-group-label">{label}</span>{items.map((conversation) => <button className={`conversation-item ${selected === conversation.id ? "active" : ""}`} key={conversation.id} onClick={() => onSelect(conversation.id)}><span className="conversation-item-title">{conversation.title || "Untitled conversation"}</span><small>{formatDate(conversation.updated_at)}</small></button>)}</div> : null)}{!filtered.length && <EmptyState title="No matches" description="Try a different conversation search." />}</div>;
}

function groupConversations(conversations: Conversation[]) {
  const now = new Date();
  const groups: Record<string, Conversation[]> = { Today: [], Yesterday: [], "Previous 7 days": [], Older: [] };
  conversations.forEach((conversation) => {
    const days = Math.floor((now.getTime() - new Date(conversation.updated_at).getTime()) / 86400000);
    groups[days === 0 ? "Today" : days === 1 ? "Yesterday" : days < 8 ? "Previous 7 days" : "Older"].push(conversation);
  });
  return groups;
}

function ToolActivity({ tools, pending }: { tools: ToolExecutionSummary[]; pending?: boolean }) {
  if (!tools.length && !pending) return null;
  return <details className="tool-activity" open={pending}><summary><span className={`activity-orb ${pending ? "working" : "complete"}`}>{pending ? <Sparkles size={14} /> : <Check size={14} />}</span><span>{pending ? "Preparing your response…" : `${tools.length} ${tools.length === 1 ? "step" : "steps"} completed`}</span><ChevronDown size={15} /></summary><div className="tool-activity-list">{tools.map((tool, index) => <div className="tool-activity-item" key={`${tool.tool_name}-${index}`}><span className={`tool-dot ${tool.success ? "success" : "failed"}`} />{toolLabels[tool.tool_name] ?? tool.tool_name}<span className="tool-compatibility-label">{tool.tool_name === "retrieve_payment_policy" ? "Policy retrieval" : tool.tool_name}: {tool.success ? "complete" : "failed"}</span><b>{tool.success ? "Complete" : "Failed"}</b></div>)}</div></details>;
}

function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return <details className="source-list"><summary><FileText size={15} /><span>Policy evidence <b>{citations.length}</b></span><ChevronDown size={15} /></summary><div>{citations.map((citation) => <article key={`${citation.document_id}-${citation.chunk_index}`}><div className="source-heading"><strong>{citation.document_title}</strong><small>Page {citation.page_number ?? "—"} · Chunk {citation.chunk_index}</small></div><p>{citation.relevant_excerpt}</p></article>)}</div></details>;
}

function Message({ message }: { message: ChatMessage }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    void navigator.clipboard?.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }
  return <div className={`message-row ${message.role === "user" ? "user" : "assistant"}`}><div className="message-content"><div className="message-meta"><span>{message.role === "user" ? "You" : "PayFlow Copilot"}</span><small>{formatDate(message.created_at)}</small>{message.role === "assistant" && <button onClick={copy} aria-label="Copy response">{copied ? <Check size={13} /> : <Clipboard size={13} />}</button>}</div><div className="message-bubble">{message.role === "assistant" ? <MarkdownText content={message.content} /> : <p>{message.content}</p>}</div></div></div>;
}

export function CopilotPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>();
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string>();
  const [lastResponse, setLastResponse] = useState<ChatMessageResponse>();
  const [searchParams] = useSearchParams();
  const messagesEnd = useRef<HTMLDivElement>(null);
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: async () => (await api.get<Conversation[]>("/chat/conversations")).data });
  const selected = selectedId ?? conversations.data?.[0]?.id;
  const messages = useQuery({ queryKey: ["conversation-messages", selected], enabled: Boolean(selected), queryFn: async () => (await api.get<ChatMessage[]>(`/chat/conversations/${selected}/messages`)).data });
  const createConversation = useMutation({ mutationFn: async () => (await api.post<Conversation>("/chat/conversations", {})).data, onSuccess: (conversation) => { setSelectedId(conversation.id); setSidebarOpen(false); void queryClient.invalidateQueries({ queryKey: ["conversations"] }); } });
  const sendMessage = useMutation({ mutationFn: async (content: string) => (await api.post<ChatMessageResponse>(`/chat/conversations/${selected}/messages`, { content })).data, onSuccess: (response) => { setLastResponse(response); setDraft(""); void queryClient.invalidateQueries({ queryKey: ["conversation-messages", selected] }); void queryClient.invalidateQueries({ queryKey: ["conversations"] }); } });
  useEffect(() => { const transactionId = searchParams.get("transactionId"); if (transactionId && !draft) setDraft(`Help me understand transaction ${transactionId}.`); }, [draft, searchParams]);
  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.data, sendMessage.isPending]);
  useEffect(() => {
    if (selected && pendingPrompt && !createConversation.isPending && !sendMessage.isPending) {
      setDraft(pendingPrompt);
      setPendingPrompt(undefined);
      sendMessage.mutate(pendingPrompt);
    }
  }, [createConversation.isPending, pendingPrompt, selected, sendMessage]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (!selected || !content || sendMessage.isPending) return;
    sendMessage.mutate(content);
  }
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
  }
  function selectSuggestion(prompt: string) {
    if (!selected) { setPendingPrompt(prompt); createConversation.mutate(); return; }
    sendMessage.mutate(prompt);
  }
  const responseMessages = lastResponse ? [lastResponse.user_message, lastResponse.assistant_message] : [];
  const displayedMessages = lastResponse && !messages.data?.some((message) => message.id === lastResponse.assistant_message.id) ? [...(messages.data ?? []), ...responseMessages] : (messages.data ?? []);
  if (conversations.isError) return <ErrorState message={getApiError(conversations.error)} onRetry={() => void conversations.refetch()} />;
  const title = selected ? conversations.data?.find((item) => item.id === selected)?.title || "Payment support" : "New conversation";
  return <div className="copilot-workspace">
    <aside className={`copilot-sidebar ${sidebarOpen ? "open" : ""}`}><div className="copilot-sidebar-header"><div><span className="eyebrow">Workspace</span><h3>Conversations</h3></div><button className="icon-button copilot-close" onClick={() => setSidebarOpen(false)} aria-label="Close conversations"><X size={18} /></button></div><Button className="new-chat-button" onClick={() => createConversation.mutate()} disabled={createConversation.isPending}><Plus size={16} /> New chat</Button>{createConversation.isError && <div className="form-error" role="alert">{getApiError(createConversation.error, "Could not create a conversation.")}</div>}{conversations.isLoading ? <div className="loading-lines"><span /><span /><span /></div> : conversations.data?.length ? <ConversationHistory conversations={conversations.data} selected={selected} search={search} onSearch={setSearch} onSelect={(id) => { setSelectedId(id); setLastResponse(undefined); setSidebarOpen(false); }} /> : <EmptyState title="No conversations yet" description="Start a conversation with your payment copilot." />}</aside>
    {sidebarOpen && <button className="copilot-backdrop" onClick={() => setSidebarOpen(false)} aria-label="Close conversations" />}
    <Card className="chat-panel"><div className="chat-header"><button className="icon-button copilot-menu" onClick={() => setSidebarOpen(true)} aria-label="Open conversations"><Menu size={19} /></button><div><span className="eyebrow">AI Copilot</span><h2>{title}</h2></div><span className="copilot-online"><span className="online-dot" /><Sparkles size={14} /> Grounded in your data</span></div>
      {!selected ? <Welcome onSelect={selectSuggestion} onNew={() => createConversation.mutate()} loading={createConversation.isPending} /> : <><div className="message-list">{messages.isLoading ? <div className="loading-lines"><span /><span /><span /></div> : messages.isError ? <ErrorState message={getApiError(messages.error)} onRetry={() => void messages.refetch()} /> : displayedMessages.map((message) => message.role === "tool" ? null : <Message message={message} key={message.id} />)}{lastResponse && <><ToolActivity tools={lastResponse.tool_executions} /><Sources citations={lastResponse.citations} /></>}{sendMessage.isPending && <ToolActivity tools={[]} pending />}{sendMessage.isError && <div className="form-error" role="alert">{getApiError(sendMessage.error, "The assistant could not respond.")} <button onClick={() => { if (draft.trim()) sendMessage.mutate(draft.trim()); }}>Retry</button></div>}<div ref={messagesEnd} /></div>{lastResponse && <FollowUps onSelect={selectSuggestion} />}</>}
      <form className="composer" onSubmit={submit}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleKeyDown} placeholder={selected ? "Ask about a transaction, payment failure, or policy…" : "Start a chat to ask your payment copilot…"} aria-label="Message" disabled={!selected || sendMessage.isPending} /><Button type="submit" disabled={!selected || !draft.trim() || sendMessage.isPending} aria-label="Send message">{sendMessage.isPending ? <Sparkles size={17} /> : <Send size={17} />}</Button></form><div className="chat-footnote">Enter to send · Shift + Enter for a new line</div></Card>
  </div>;
}

function Welcome({ onSelect, onNew, loading }: { onSelect: (prompt: string) => void; onNew: () => void; loading: boolean }) {
  return <div className="copilot-welcome"><div className="welcome-mark"><Bot size={27} /></div><span className="eyebrow">Payment intelligence</span><h3>Your Payment Intelligence Assistant</h3><p>Investigate transactions, understand payment failures, and get answers backed by your payment policies.</p><div className="suggestion-grid">{suggestions.map(({ title, example, prompt, icon: Icon }) => <button className="suggestion-card" key={title} onClick={() => onSelect(prompt)}><span className="suggestion-icon"><Icon size={17} /></span><strong>{title}</strong><small>{example}</small><ChevronDown size={15} /></button>)}</div><Button onClick={onNew} disabled={loading}><Plus size={16} /> Start a blank chat</Button></div>;
}

function FollowUps({ onSelect }: { onSelect: (prompt: string) => void }) {
  return <div className="follow-ups"><span>Continue exploring</span><div><button onClick={() => onSelect("Explain this failure in simpler terms.")}>Explain this in simpler terms</button><button onClick={() => onSelect("Can I safely retry this payment?")}>Can I safely retry this payment?</button><button onClick={() => onSelect("Show me the related refund policy.")}>Show related policy</button></div></div>;
}
