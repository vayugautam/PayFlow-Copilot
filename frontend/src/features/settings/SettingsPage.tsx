import { useEffect, useState, type ReactNode } from "react";
import { Bell, Check, ChevronRight, CreditCard, KeyRound, Monitor, Moon, ShieldCheck, Sun, UserRound } from "lucide-react";
import { Card } from "../../components/ui";
import { useAuth } from "../auth/AuthContext";

type Preferences = {
  emailUpdates: boolean;
  compactTables: boolean;
  theme: "light" | "system";
};

const PREFERENCES_KEY = "payflow_workspace_preferences";
const defaultPreferences: Preferences = { emailUpdates: true, compactTables: false, theme: "light" };

function readPreferences(): Preferences {
  try {
    const stored = JSON.parse(localStorage.getItem(PREFERENCES_KEY) ?? "null") as Partial<Preferences> | null;
    return {
      emailUpdates: stored?.emailUpdates ?? defaultPreferences.emailUpdates,
      compactTables: stored?.compactTables ?? defaultPreferences.compactTables,
      theme: stored?.theme === "system" ? "system" : "light",
    };
  } catch {
    return defaultPreferences;
  }
}

export function SettingsPage() {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState<Preferences>(readPreferences);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
    setSaved(true);
    const timer = window.setTimeout(() => setSaved(false), 1400);
    return () => window.clearTimeout(timer);
  }, [preferences]);

  function update<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    setPreferences((current) => ({ ...current, [key]: value }));
  }

  return <div className="settings-page page-stack">
    <div className="settings-intro">
      <div><span className="eyebrow">Workspace</span><h2>Settings</h2><p className="muted">Manage how PayFlow Copilot looks and keeps you informed.</p></div>
      {saved && <span className="save-indicator"><Check size={15} /> Preferences saved</span>}
    </div>
    <div className="settings-layout">
      <main className="settings-main">
        <Card className="settings-card profile-card"><div className="settings-card-heading"><div className="settings-icon purple"><UserRound size={18} /></div><div><h3>Profile</h3><p className="muted">Your signed-in workspace identity.</p></div></div><div className="profile-summary"><span className="profile-large-avatar">{user?.email.slice(0, 1).toUpperCase()}</span><div><strong>{user?.email}</strong><span>Authenticated PayFlow Copilot account</span></div></div><div className="settings-note"><ShieldCheck size={16} /><span>Your password and authentication credentials are managed securely by the backend.</span></div></Card>
        <Card className="settings-card"><div className="settings-card-heading"><div className="settings-icon blue"><Monitor size={18} /></div><div><h3>Workspace preferences</h3><p className="muted">Personalize your day-to-day dashboard experience.</p></div></div><div className="preference-list"><PreferenceRow icon={<Bell size={16} />} title="Product updates" description="Keep workspace notifications enabled for important activity." control={<Toggle checked={preferences.emailUpdates} onChange={(value) => update("emailUpdates", value)} />} /><PreferenceRow icon={<CreditCard size={16} />} title="Compact transaction tables" description="Show more payment activity in the same amount of space." control={<Toggle checked={preferences.compactTables} onChange={(value) => update("compactTables", value)} />} /><div className="preference-row"><span className="preference-leading"><span className="row-icon"><Sun size={16} /></span><span><strong>Appearance</strong><small>Choose the visual density for this browser.</small></span></span><div className="segmented-control"><button className={preferences.theme === "light" ? "selected" : ""} onClick={() => update("theme", "light")}><Sun size={14} /> Light</button><button className={preferences.theme === "system" ? "selected" : ""} onClick={() => update("theme", "system")}><Moon size={14} /> System</button></div></div></div></Card>
        <Card className="settings-card"><div className="settings-card-heading"><div className="settings-icon green"><KeyRound size={18} /></div><div><h3>Security and sessions</h3><p className="muted">Understand how this browser session is protected.</p></div></div><div className="security-list"><div><ShieldCheck size={16} /><span><strong>Session-only sign-in</strong><small>Your access token is kept in this browser tab and cleared when you sign out.</small></span></div><div><LockIcon /><span><strong>No password storage</strong><small>PayFlow Copilot never stores your password in the browser.</small></span></div></div></Card>
      </main>
      <aside className="settings-sidebar">
        <Card className="settings-card integration-card"><div className="settings-card-heading"><div className="settings-icon amber"><CreditCard size={18} /></div><div><h3>Connected services</h3><p className="muted">Configured for this environment.</p></div></div><IntegrationRow name="PayFlow API" detail="Authenticated backend connection" status="Connected" connected /><IntegrationRow name="Razorpay test checkout" detail={import.meta.env.VITE_RAZORPAY_KEY_ID ? "Test mode key configured" : "Test mode key not configured"} status={import.meta.env.VITE_RAZORPAY_KEY_ID ? "Ready" : "Not configured"} connected={Boolean(import.meta.env.VITE_RAZORPAY_KEY_ID)} /></Card>
        <Card className="settings-card help-card"><span className="eyebrow">Need help?</span><h3>Review your payment activity</h3><p className="muted">Use Transactions for payment details, Disputes for case management, and Audit Logs for a read-only activity trail.</p><a href="/transactions">Go to transactions <ChevronRight size={15} /></a></Card>
      </aside>
    </div>
  </div>;
}

function PreferenceRow({ icon, title, description, control }: { icon: ReactNode; title: string; description: string; control: ReactNode }) {
  return <div className="preference-row"><span className="preference-leading"><span className="row-icon">{icon}</span><span><strong>{title}</strong><small>{description}</small></span></span>{control}</div>;
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return <button className={`toggle ${checked ? "on" : ""}`} role="switch" aria-checked={checked} aria-label={checked ? "Turn off" : "Turn on"} onClick={() => onChange(!checked)}><span /></button>;
}

function IntegrationRow({ name, detail, status, connected }: { name: string; detail: string; status: string; connected: boolean }) {
  return <div className="integration-row"><span className={`integration-dot ${connected ? "connected" : ""}`} /><span><strong>{name}</strong><small>{detail}</small></span><b>{status}</b></div>;
}

function LockIcon() {
  return <KeyRound size={16} />;
}
