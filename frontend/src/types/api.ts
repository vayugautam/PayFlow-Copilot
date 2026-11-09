export type User = {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
};

export type TokenResponse = { access_token: string; token_type: string };

export type Transaction = {
  id: string;
  amount: string;
  currency: string;
  status: "successful" | "failed" | "pending" | "refunded";
  merchant: string;
  description: string | null;
  failure_code: string | null;
  payment_method: string | null;
  provider_order_id: string | null;
  provider_payment_id: string | null;
  failure_description: string | null;
  failure_source: string | null;
  failure_step: string | null;
  failure_reason: string | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
};

export type TransactionPage = {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type Dispute = {
  id: string;
  user_id: string;
  transaction_id: string;
  conversation_id: string | null;
  title: string;
  description: string;
  reason: string;
  status: "DRAFT" | "SUBMITTED" | "UNDER_REVIEW" | "RESOLVED" | "REJECTED" | "CANCELLED";
  evidence: Record<string, unknown> | null;
  resolution: string | null;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  resolved_at: string | null;
};

export type DisputePage = { items: Dispute[]; total: number; page: number; page_size: number };

export type DisputeDraftRequest = {
  transaction_id: string;
  user_claim: string;
  conversation_id?: string | null;
};

export type DisputeUpdateRequest = {
  title?: string;
  description?: string;
  reason?: Dispute["reason"];
  evidence?: Record<string, unknown> | null;
};

export type AuditLog = {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown> | null;
  created_at: string;
};

export type AuditLogPage = {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
};

export type Conversation = {
  id: string;
  title: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "tool" | string;
  content: string;
  tool_name: string | null;
  created_at: string;
};

export type Citation = {
  document_id: string;
  document_title: string;
  page_number: number | null;
  chunk_index: number;
  relevant_excerpt: string;
};

export type ToolExecutionSummary = {
  tool_name: string;
  success: boolean;
};

export type ChatMessageRequest = { content: string };

export type ChatMessageResponse = {
  conversation_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  citations: Citation[];
  tool_executions: ToolExecutionSummary[];
  created_at: string;
};

export type TransactionAnalysis = {
  transaction_id: string;
  transaction_status: string;
  failure_code: string | null;
  category: string;
  title: string;
  explanation: string;
  recommended_actions: string[];
  retry_eligibility: "retry_now" | "retry_after_action" | "verify_status_first" | "do_not_retry" | "unknown";
  severity: "low" | "medium" | "high" | "critical";
};
