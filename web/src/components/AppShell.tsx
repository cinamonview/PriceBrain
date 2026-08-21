import { NavLink, Outlet } from "react-router-dom";
import { formatPrimaryRole, useAuth } from "../auth/AuthContext";
import { connectionLabel, useConnectionStatus } from "../auth/ConnectionContext";
import { getApiBaseUrl } from "../api/operationsApi";

const NAV_ITEMS = [
  { to: "/", label: "Command Center", end: true },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/investigation", label: "Investigation" },
  { to: "/remediation", label: "Remediation" },
  { to: "/execution", label: "Execution History" },
  { to: "/audit", label: "Audit" },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const { status: connectionStatus } = useConnectionStatus();
  const apiBase = getApiBaseUrl() || "(same origin / dev proxy)";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">PriceBrain</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div>
            <div className="topbar-title">Operations Dashboard</div>
            <div className="topbar-subtitle">Backend: {apiBase}</div>
          </div>
          <div className="topbar-user">
            <div className={`connection-pill connection-${connectionStatus}`}>
              {connectionLabel(connectionStatus)}
            </div>
            <div>{user?.email ?? user?.uid ?? "Unknown user"}</div>
            <div className="role-pill">{formatPrimaryRole(user?.roles ?? [])}</div>
            <button type="button" onClick={() => void logout()}>
              Logout
            </button>
          </div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
