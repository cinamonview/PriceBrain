import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CommandCenterPage } from "../pages/CommandCenterPage";
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
        getCommandCenter: vi.fn(async () => ({
          generated_at: "2026-08-21T00:00:00Z",
          health: {
            dashboard: "DEGRADED",
            dashboard_reasons: ["failures"],
            execution: "HEALTHY",
            execution_reasons: [],
          },
          dashboard: {
            generated_at: "2026-08-21T00:00:00Z",
            summary: { health: "DEGRADED", reasons: [] },
            crawler: { total_targets: 1, failed_targets: 1 },
            price: { targets: 1 },
            alerts: { total: 0 },
            notifications: { sent: 0, failed: 0, skipped: 0, recent_failures: [] },
            runner: { last_cycle_status: "SUCCESS", recent_cycles: 1, recent_failed_cycles: 0 },
            audit: { recent_events: 0, event_snapshots: [] },
          },
          investigation: {
            generated_at: "2026-08-21T00:00:00Z",
            health: "DEGRADED",
            summary: { total_findings: 2, critical_count: 0, warning_count: 1 },
            findings: [],
            dashboard_summary: { health: "DEGRADED", reasons: [] },
            crawler: {},
            price: {},
            alerts: {},
            notifications: {},
            runner: {},
            audit: {},
          },
          remediation: {
            generated_at: "2026-08-21T00:00:00Z",
            health: "DEGRADED",
            summary: { actionable_actions: 1, total_actions: 1 },
            actions: [],
            total_findings: 1,
            actionable_findings: 1,
            read_errors: 0,
          },
          execution: {
            generated_at: "2026-08-21T00:00:00Z",
            health: "HEALTHY",
            health_reasons: [],
            summary: { total: 0, blocked: 0, failed: 0, mutation_count: 0 },
            entries: [],
          },
        })),
      },
      login: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(async () => "token"),
    }),
  };
});

describe("CommandCenterPage", () => {
  it("renders health cards from command center contract", async () => {
    render(
      <ConnectionProvider>
        <CommandCenterPage />
      </ConnectionProvider>,
    );

    expect(await screen.findByText("Command Center")).toBeInTheDocument();
    expect(screen.getByText("Execution Health")).toBeInTheDocument();
    expect(screen.getAllByText("DEGRADED").length).toBeGreaterThan(0);
    expect(screen.getByText("Execution History")).toBeInTheDocument();
  });
});
