import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { AppShell } from "./components/AppShell";
import { AuditPage } from "./pages/AuditPage";
import { CommandCenterPage } from "./pages/CommandCenterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ExecutionPage } from "./pages/ExecutionPage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { RemediationPage } from "./pages/RemediationPage";
import { UI } from "./utils/uiLabels";

function ProtectedRoutes() {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="login-page">{UI.loading}</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoutes />}>
        <Route index element={<CommandCenterPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/investigation" element={<InvestigationPage />} />
        <Route path="/remediation" element={<RemediationPage />} />
        <Route path="/execution" element={<ExecutionPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
