import { Bell, Bot, ChevronLeft, FileClock, LayoutDashboard, LogOut, Menu, Receipt, Scale, Settings, X } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";

const navigation = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/copilot", label: "AI Copilot", icon: Bot },
  { to: "/transactions", label: "Transactions", icon: Receipt },
  { to: "/disputes", label: "Disputes", icon: Scale },
  { to: "/audit-logs", label: "Audit Logs", icon: FileClock },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();
  const title = navigation.find((item) => location.pathname.startsWith(item.to))?.label ?? "Overview";

  return <div className="app-shell">
    <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="brand"><span className="brand-mark">P</span><span className="brand-copy">PayFlow <b>Copilot</b></span><button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18} /></button></div>
      <nav aria-label="Primary navigation">{navigation.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item" onClick={logout}><LogOut size={18} /><span>Log out</span></button><button className="collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar"><ChevronLeft size={17} className={collapsed ? "rotate" : ""} /></button></div>
    </aside>
    {mobileOpen && <button className="mobile-backdrop" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
    <div className="main-column">
      <header className="topbar"><button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu size={20} /></button><div><span className="eyebrow">Workspace</span><h1>{title}</h1></div><div className="topbar-actions"><button className="icon-button" aria-label="Notifications"><Bell size={19} /></button><div className="profile"><span className="avatar">{user?.email.slice(0, 1).toUpperCase()}</span><span className="profile-email">{user?.email}</span></div></div></header>
      <main className={`content ${location.pathname === "/copilot" ? "content-copilot" : ""}`}><Outlet /></main>
    </div>
  </div>;
}
