import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardPage } from "../pages/DashboardPage";
import { ConnectionProvider } from "../auth/ConnectionContext";

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: {
        getDashboard: vi.fn(async () => ({
          generated_at: "2026-08-21T00:00:00Z",
          summary: { health: "HEALTHY", reasons: [] },
          crawler: { total_targets: 3, failed_targets: 1, ssg_access_denied: 0, recent_failures: 1 },
          price: { targets: 3, with_price: 2, no_history: 0, invalid_price: 0 },
          alerts: { total: 2, enabled: 1, invalid: 0, recent_invalid: 0 },
          notifications: { sent: 1, failed: 0, skipped: 0, recent_failures: [] },
          runner: { last_cycle_status: "SUCCESS", recent_cycles: 1, recent_failed_cycles: 0, notification_failed: 0 },
          audit: { recent_events: 1, recent_failures: 0, recent_alert_triggered: 0, recent_runner_failed: 0 },
        })),
      },
      login: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(async () => "token"),
    }),
  };
});

describe("DashboardPage", () => {
  it("renders dashboard sections from contract", async () => {
    render(
      <ConnectionProvider>
        <DashboardPage />
      </ConnectionProvider>,
    );
    expect(await screen.findByText("대시보드")).toBeInTheDocument();
    expect(screen.getByText("크롤러")).toBeInTheDocument();
    expect(screen.getByText("가격")).toBeInTheDocument();
    expect(screen.getByText("가격 알림")).toBeInTheDocument();
    expect(screen.getByText("알림 전송")).toBeInTheDocument();
    expect(screen.getByText("실행기")).toBeInTheDocument();
    expect(screen.getByText("감사 로그")).toBeInTheDocument();
  });
});
