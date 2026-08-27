import { NavLink, Outlet } from "react-router-dom";
import { formatPrimaryRole, useAuth } from "../auth/AuthContext";
import { connectionLabel, useConnectionStatus } from "../auth/ConnectionContext";
import { getApiBaseUrl } from "../api/operationsApi";
import { UI } from "../utils/uiLabels";

const NAV_ITEMS = [
  { to: "/", label: UI.commandCenter, end: true },
  { to: "/dashboard", label: UI.dashboard },
  { to: "/investigation", label: UI.investigation },
  { to: "/remediation", label: UI.remediation },
  { to: "/execution", label: UI.executionHistory },
  { to: "/audit", label: UI.audit },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const { status: connectionStatus } = useConnectionStatus();
  const apiBase = getApiBaseUrl() || "(same origin / dev proxy)";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">{UI.appName}</div>
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
            <div className="topbar-title">{UI.operationsDashboard}</div>
            <div className="topbar-subtitle">
              {UI.backend}: {apiBase}
            </div>
          </div>
          <div className="topbar-user">
            <div className={`connection-pill connection-${connectionStatus}`}>
              {connectionLabel(connectionStatus)}
            </div>
            <div>{user?.email ?? user?.uid ?? UI.unknownUser}</div>
            <div className="role-pill">{formatPrimaryRole(user?.roles ?? [])}</div>
            <button type="button" onClick={() => void logout()}>
              {UI.logout}
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
