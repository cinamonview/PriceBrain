import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { ApiError } from "../api/operationsApi";
import { CommandCenterPage } from "../pages/CommandCenterPage";
import { ConnectionProvider } from "../auth/ConnectionContext";
import type { CommandCenterResponse } from "../api/types";

const mockResponse: CommandCenterResponse = {
  generated_at: "2026-08-21T12:30:00Z",
  health: {
    dashboard: "DEGRADED",
    dashboard_reasons: ["crawler failures"],
    execution: "CRITICAL",
    execution_reasons: ["recent execution failures"],
  },
  dashboard: {
    generated_at: "2026-08-21T12:30:00Z",
    summary: { health: "DEGRADED", reasons: ["failures"] },
    crawler: {
      total_targets: 3,
      enabled_targets: 2,
      disabled_targets: 1,
      failed_targets: 1,
      ssg_access_denied: 1,
      high_priority_failed: 0,
      recent_successes: 2,
      recent_failures: 1,
      by_mall: {},
      recent_failure_targets: [],
    },
    price: {
      targets: 3,
      with_price: 2,
      without_price: 1,
      price_down: 0,
      price_up: 0,
      unchanged: 2,
      no_history: 1,
      invalid_price: 0,
    },
    alerts: {
      total: 2,
      enabled: 1,
      disabled: 1,
      triggered_recently: 1,
      never_triggered: 1,
      invalid: 0,
      by_type: {},
      recent_invalid: 0,
    },
    notifications: {
      sent: 2,
      failed: 1,
      skipped: 0,
      by_channel: {},
      recent_failures: [{ channel: "email" }],
    },
    runner: {
      last_cycle_status: "FAILED",
      last_run_at: "2026-08-21T12:00:00Z",
      duration_seconds: 1.2,
      total_alerts: 2,
      evaluated: 2,
      triggered: 1,
      notification_sent: 1,
      notification_failed: 1,
      recent_cycles: 3,
      recent_failed_cycles: 1,
    },
    audit: {
      recent_events: 2,
      recent_failures: 1,
      recent_alert_triggered: 1,
      recent_notification_failed: 1,
      recent_runner_failed: 0,
      event_snapshots: [
        {
          summary: "notification failed",
          event: {
            event_id: "audit-1",
            event_type: "NOTIFICATION_FAILED",
            occurred_at: "2026-08-21T12:10:00Z",
            alert_id: "alert-1",
            status: "FAILED",
            message: "Notification failed",
            metadata: { approval_token: "secret-token", api_key: "key-123" },
          },
        },
      ],
    },
  },
  investigation: {
    generated_at: "2026-08-21T12:30:00Z",
    health: "DEGRADED",
    summary: {
      total_findings: 3,
      critical_count: 1,
      warning_count: 1,
      error_count: 1,
      info_count: 0,
      areas: { crawler: 1, runner: 1 },
      read_errors: 0,
    },
    findings: [
      {
        finding_id: "f-critical",
        severity: "CRITICAL",
        area: "runner",
        code: "RUNNER_CYCLE_FAILED",
        title: "Runner cycle failed",
        message: "Repeated runner cycle failure",
        metadata: {},
      },
      {
        finding_id: "f-error",
        severity: "ERROR",
        area: "crawler",
        code: "CRAWLER_HTTP_ERROR",
        title: "Crawler HTTP error",
        message: "HTTP error observed",
        target_id: "ssg_123",
        metadata: {},
      },
      {
        finding_id: "f-warning",
        severity: "WARNING",
        area: "crawler",
        code: "SSG_ACCESS_DENIED",
        title: "SSG access denied",
        message: "Access denied",
        metadata: {},
      },
    ],
    dashboard_summary: { health: "DEGRADED", reasons: [] },
    crawler: {},
    price: {},
    alerts: {},
    notifications: {},
    runner: {},
    audit: {},
  },
  remediation: {
    generated_at: "2026-08-21T12:30:00Z",
    health: "DEGRADED",
    summary: {
      total_actions: 1,
      actionable_actions: 1,
      no_action_count: 0,
      by_priority: { HIGH: 1 },
      by_area: { runner: 1 },
      read_errors: 0,
    },
    actions: [
      {
        action_id: "action-1",
        action_type: "REVIEW_RUNNER",
        priority: "HIGH",
        risk: "HIGH",
        finding_id: "f-critical",
        area: "runner",
        title: "Review runner failure",
        reason: "Repeated runner failure",
        recommended_steps: [],
        preconditions: [],
        human_approval_required: true,
        auto_executable: false,
        metadata: {},
      },
    ],
    total_findings: 1,
    actionable_findings: 1,
    read_errors: 0,
  },
  execution: {
    generated_at: "2026-08-21T12:30:00Z",
    health: "CRITICAL",
    health_reasons: ["recent failures"],
    summary: {
      total: 2,
      planned: 1,
      dry_run: 0,
      approved: 0,
      executed: 0,
      blocked: 0,
      failed: 1,
      skipped: 0,
      mutation_count: 0,
      approval_failures: 0,
      recent_failures: 1,
      by_action_type: {},
      by_area: {},
      read_errors: 0,
    },
    entries: [
      {
        entry: {
          execution_id: "exec-failed",
          action_id: "action-1",
          action_type: "REVIEW_RUNNER",
          mode: "EXECUTE",
          status: "FAILED",
          priority: "HIGH",
          risk: "HIGH",
          area: "runner",
          title: "Failed execution",
          message: "Execution failed",
          mutation_performed: false,
          approval_verified: false,
          occurred_at: "2026-08-21T12:20:00Z",
          metadata: {},
        },
      },
    ],
  },
};

let getCommandCenter = vi.fn(async () => mockResponse);

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: {
        getCommandCenter,
      },
      login: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(async () => "mock-id-token"),
    }),
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ConnectionProvider>
        <CommandCenterPage />
      </ConnectionProvider>
    </MemoryRouter>,
  );
}

function collectSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      if (name === "node_modules" || name === "dist") {
        continue;
      }
      files.push(...collectSourceFiles(path));
      continue;
    }
    if (/\.(ts|tsx)$/.test(name)) {
      files.push(path);
    }
  }
  return files;
}

describe("CommandCenterPage", () => {
  afterEach(() => {
    cleanup();
    getCommandCenter = vi.fn(async () => mockResponse);
  });

  it("renders health summary and area cards", async () => {
    renderPage();
    expect(await screen.findByText("PriceBrain 운영 센터")).toBeInTheDocument();
    expect(screen.getByText("전체 상태")).toBeInTheDocument();
    expect(screen.getAllByText("일부 문제").length).toBeGreaterThan(0);
    expect(screen.getAllByText("치명적").length).toBeGreaterThan(0);
    expect(screen.getAllByText("크롤러").length).toBeGreaterThan(0);
    expect(screen.getAllByText("가격").length).toBeGreaterThan(0);
    expect(screen.getAllByText("알림 전송").length).toBeGreaterThan(0);
    expect(screen.getAllByText("실행기").length).toBeGreaterThan(0);
    expect(screen.getAllByText("실행").length).toBeGreaterThan(0);
    expect(screen.getByText(/초마다 자동 새로고침/)).toBeInTheDocument();
  });

  it("highlights critical, error, and warning findings from API data", async () => {
    renderPage();
    await screen.findByText("치명적 / 실패 하이라이트");
    expect(screen.getByText("RUNNER_CYCLE_FAILED")).toBeInTheDocument();
    expect(screen.getByText("CRAWLER_HTTP_ERROR")).toBeInTheDocument();
    expect(screen.getByText("SSG_ACCESS_DENIED")).toBeInTheDocument();
  });

  it("shows crawler, price, alert, notification, runner, audit, execution, remediation summaries", async () => {
    renderPage();
    await screen.findByText("최근 실행 이력");
    expect(screen.getByText("Execution failed")).toBeInTheDocument();
    expect(screen.getAllByText("Notification failed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("REVIEW_RUNNER").length).toBeGreaterThan(0);
    expect(screen.getByText(/승인 필요: 예/)).toBeInTheDocument();
  });

  it("filters findings with failures-only, area, severity, and search", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("RUNNER_CYCLE_FAILED");

    await user.click(screen.getByLabelText("실패 항목만"));
    expect(screen.getByText("RUNNER_CYCLE_FAILED")).toBeInTheDocument();
    expect(screen.queryByText("SSG_ACCESS_DENIED")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("실패 항목만"));
    await user.selectOptions(screen.getByLabelText("영역 필터"), "crawler");
    expect(screen.getByText("SSG_ACCESS_DENIED")).toBeInTheDocument();
    expect(screen.queryByText("RUNNER_CYCLE_FAILED")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("영역 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("심각도 필터"), "WARNING");
    expect(screen.getByText("SSG_ACCESS_DENIED")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("심각도 필터"), "ALL");
    await user.type(screen.getByLabelText("운영 센터 검색"), "HTTP");
    expect(screen.getByText("CRAWLER_HTTP_ERROR")).toBeInTheDocument();
  });

  it("provides navigation links to investigation, remediation, execution, and audit", async () => {
    renderPage();
    await screen.findByText("PriceBrain 운영 센터");
    expect(screen.getAllByRole("link", { name: "조사 보기" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "조치 계획 보기" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "실행 이력 보기" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "감사 로그 보기" }).length).toBeGreaterThan(0);
  });

  it("redacts sensitive audit metadata in list rendering path", async () => {
    renderPage();
    await screen.findAllByText("Notification failed");
    expect(screen.queryByText("secret-token")).not.toBeInTheDocument();
    expect(screen.queryByText("key-123")).not.toBeInTheDocument();
  });

  it("shows empty execution list when no entries", async () => {
    getCommandCenter = vi.fn(async () => ({
      ...mockResponse,
      execution: { ...mockResponse.execution, entries: [] },
    }));
    renderPage();
    expect(await screen.findByText("최근 실행 이력이 없습니다.")).toBeInTheDocument();
  });
});

describe("CommandCenterPage error states", () => {
  afterEach(() => {
    cleanup();
    getCommandCenter = vi.fn(async () => mockResponse);
  });

  it("shows 401 message", async () => {
    getCommandCenter = vi.fn(async () => {
      throw new ApiError(401, "인증이 필요합니다.");
    });
    renderPage();
    expect(await screen.findByText("인증이 필요합니다.")).toBeInTheDocument();
  });

  it("shows 403 message", async () => {
    getCommandCenter = vi.fn(async () => {
      throw new ApiError(403, "이 작업을 볼 권한이 없습니다.");
    });
    renderPage();
    expect(await screen.findByText("운영 센터 정보를 볼 권한이 없습니다.")).toBeInTheDocument();
  });

  it("shows 500 message and retry", async () => {
    getCommandCenter = vi.fn(async () => {
      throw new ApiError(500, "운영 정보를 불러오지 못했습니다.");
    });
    renderPage();
    expect(await screen.findByText("운영 센터 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("CommandCenterPage loading", () => {
  afterEach(() => {
    cleanup();
    getCommandCenter = vi.fn(async () => mockResponse);
  });

  it("shows loading skeleton before data arrives", async () => {
    getCommandCenter = vi.fn(
      () =>
        new Promise<CommandCenterResponse>((resolve) => {
          setTimeout(() => resolve(mockResponse), 100);
        }),
    );
    renderPage();
    expect(document.querySelector(".investigation-loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("PriceBrain 운영 센터")).toBeInTheDocument());
  });
});

describe("CommandCenterPage read-only security", () => {
  it("does not expose execute controls", async () => {
    renderPage();
    await screen.findByText("PriceBrain 운영 센터");
    expect(screen.queryByRole("button", { name: /^execute$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run$/i })).not.toBeInTheDocument();
  });

  it("does not include mutation API calls in frontend source", () => {
    const srcRoot = join(process.cwd(), "src");
    const forbiddenPatterns = [
      /method:\s*["']POST["']/i,
      /method:\s*["']PUT["']/i,
      /method:\s*["']PATCH["']/i,
      /method:\s*["']DELETE["']/i,
      /executeRemediation/i,
      /execute_plan/i,
      /issue_test_approval_token/i,
    ];
    const hits: string[] = [];
    for (const file of collectSourceFiles(srcRoot)) {
      if (file.includes(".test.")) {
        continue;
      }
      const content = readFileSync(file, "utf8");
      for (const pattern of forbiddenPatterns) {
        if (pattern.test(content)) {
          hits.push(`${file}: ${pattern}`);
        }
      }
    }
    expect(hits).toEqual([]);
  });
});
