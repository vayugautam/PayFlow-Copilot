import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button, Card } from "../../components/ui";
import { getApiError } from "../../lib/api";
import { useAuth } from "./AuthContext";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const isLogin = mode === "login";
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    if (!email.includes("@")) return setError("Enter a valid email address.");
    if (password.length < (isLogin ? 1 : 8)) return setError(isLogin ? "Enter your password." : "Password must be at least 8 characters.");
    try {
      setBusy(true);
      if (isLogin) { await login(email.trim(), password); navigate((location.state as { from?: string } | null)?.from ?? "/dashboard", { replace: true }); }
      else { await register(email.trim(), password); setSuccess("Account created. You can now sign in."); }
    } catch (reason) { setError(getApiError(reason, isLogin ? "Sign in failed." : "Registration failed.")); } finally { setBusy(false); }
  }
  return <div className="auth-page"><div className="auth-brand"><span className="brand-mark">P</span> PayFlow <b>Copilot</b></div><Card className="auth-card"><span className="eyebrow">Secure workspace</span><h1>{isLogin ? "Welcome back" : "Create your account"}</h1><p className="muted">{isLogin ? "Sign in to review your payment operations." : "Start with a secure workspace for payment support."}</p><form onSubmit={submit}><label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label><label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={isLogin ? "current-password" : "new-password"} /></label>{error && <div className="form-error" role="alert">{error}</div>}{success && <div className="form-success" role="status">{success}</div>}<Button type="submit" disabled={busy}>{busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}</Button></form><p className="auth-switch">{isLogin ? "New to PayFlow?" : "Already have an account?"} <Link to={isLogin ? "/register" : "/login"}>{isLogin ? "Create an account" : "Sign in"}</Link></p></Card><p className="auth-footnote">Bearer-token authentication · Your session stays in this browser tab.</p></div>;
}
