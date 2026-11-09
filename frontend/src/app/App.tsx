import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { AuthPage } from "../features/auth/AuthPages";
import { useAuth } from "../features/auth/AuthContext";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { CopilotPage } from "../features/copilot/CopilotPage";
import { TransactionDetailPage, TransactionsPage } from "../features/transactions/TransactionsPage";
import { DisputeDetailPage, DisputesPage } from "../features/disputes/DisputesPage";
import { AuditLogsPage } from "../features/audit/AuditLogsPage";

function Protected() {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <div className="full-loading">Loading your workspace…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <AppShell />;
}

export function App() {
  return <Routes><Route path="/login" element={<AuthPage mode="login" />} /><Route path="/register" element={<AuthPage mode="register" />} /><Route element={<Protected />}><Route index element={<Navigate to="/dashboard" replace />} /><Route path="/dashboard" element={<DashboardPage />} /><Route path="/transactions" element={<TransactionsPage />} /><Route path="/transactions/:transactionId" element={<TransactionDetailPage />} /><Route path="/copilot" element={<CopilotPage />} /><Route path="/disputes" element={<DisputesPage />} /><Route path="/disputes/:disputeId" element={<DisputeDetailPage />} /><Route path="/audit-logs" element={<AuditLogsPage />} /><Route path="/settings" element={<SettingsPage />} /></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes>;
}
