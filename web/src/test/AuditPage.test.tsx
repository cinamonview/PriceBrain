import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { ApiError } from "../api/operationsApi";
import { AuditPage } from "../pages/AuditPage";
import { ConnectionProvider } from "../auth/ConnectionContext";
import type { AuditEvent, AuditEventSnapshot, AuditResponse } from "../api/types";

function makeEvent(
  overrides: Partial<AuditEvent> & Pick<AuditEvent, "event_id" | "event_type">,
): AuditEvent {
  return {
    occurred_at: "2026-08-21T10:00:00Z",
    metadata: {},
    ...overrides,
  };
}

const mockSnapshots: AuditEventSnapshot[] = [
  {
    summary: "alert=a1 target=ssg_1",
    event: makeEvent({
      event_id: "evt-triggered",
      event_type: "ALERT_TRIGGERED",
      alert_id: "a1",
      target_id: "ssg_1",
      message: "Alert triggered",
      occurred_at: "2026-08-21T12:00:00Z",
      metadata: { finding_id: "finding-1" },
    }),
  },
  {
    summary: "notification failed",
    event: makeEvent({
      event_id: "evt-failed",
      event_type: "NOTIFICATION_FAILED",
      alert_id: "a2",
      status: "FAILED",
      message: "Notification failed",
      occurred_at: "2026-08-21T11:00:00Z",
      metadata: {
        approval_token: "secret-token",
        api_key: "key-123",
        webhook: "https://hooks.example/secret",
        private_key: "pk-test",
        authorization: "Bearer secret",
      },
    }),
  },
  {
    summary: "runner completed",
    event: makeEvent({
      event_id: "evt-runner",
      event_type: "RUNNER_CYCLE_COMPLETED",
      status: "COMPLETED",
      message: "Runner cycle completed",
      occurred_at: "2026-08-21T09:00:00Z",
      metadata: { execution_id: "exec-1", action_id: "action-1" },
    }),
  },
];

const mockResponse: AuditResponse = {
  generated_at: "2026-08-21T12:30:00Z",
  health: "DEGRADED",
  health_reasons: ["recent failures"],
  summary: {
    total: 3,
    recent: 3,
    by_type: {
      ALERT_TRIGGERED: 1,
      NOTIFICATION_FAILED: 1,
      RUNNER_CYCLE_COMPLETED: 1,
    },
    by_status: { TRIGGERED: 1, FAILED: 1, COMPLETED: 1 },
    by_channel: {},
    by_area: { alert: 1, notification: 1, runner: 1 },
    alert_events: 1,
    notification_events: 1,
    runner_events: 1,
    failure_events: 1,
    read_errors: 0,
  },
  events: mockSnapshots,
};

let getAudit = vi.fn(async () => mockResponse);

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: {
        getAudit,
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
        <AuditPage />
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

describe("AuditPage", () => {
  afterEach(() => {
    cleanup();
    getAudit = vi.fn(async () => mockResponse);
  });

  it("renders audit summary and health", async () => {
    renderPage();
    expect(await screen.findByText("PriceBrain 감사 로그")).toBeInTheDocument();
    expect(screen.getByText("감사 로그 상태")).toBeInTheDocument();
    expect(screen.getAllByText("일부 문제").length).toBeGreaterThan(0);
    expect(screen.getByText("전체 이벤트")).toBeInTheDocument();
    expect(screen.getByText("실패 이벤트")).toBeInTheDocument();
    expect(screen.getAllByText("알림 발생").length).toBeGreaterThan(0);
  });

  it("filters by event type, severity, area, target, alert, failures-only, search, and sort", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("evt-triggered");

    await user.selectOptions(screen.getByLabelText("이벤트 유형 필터"), "NOTIFICATION_FAILED");
    expect(screen.getByText("evt-failed")).toBeInTheDocument();
    expect(screen.queryByText("evt-triggered")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("이벤트 유형 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("심각도 필터"), "ERROR");
    expect(screen.getByText("evt-failed")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("심각도 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("영역 필터"), "runner");
    expect(screen.getByText("evt-runner")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("영역 필터"), "ALL");
    await user.type(screen.getByLabelText("대상 필터"), "ssg_1");
    expect(screen.getByText("evt-triggered")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("대상 필터"));
    await user.type(screen.getByLabelText("알림 필터"), "a2");
    expect(screen.getByText("evt-failed")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("알림 필터"));
    await user.click(screen.getByLabelText("실패 항목만"));
    expect(screen.getByText("evt-failed")).toBeInTheDocument();

    await user.click(screen.getByLabelText("실패 항목만"));
    await user.type(screen.getByLabelText("감사 로그 검색"), "runner");
    expect(screen.getByText("evt-runner")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("감사 로그 검색"));
    await user.selectOptions(screen.getByLabelText("정렬 순서"), "OLDEST");
    expect(screen.getByText("evt-runner")).toBeInTheDocument();
  });

  it("opens detail panel with redacted metadata and navigation links", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("evt-failed");
    await user.click(screen.getByText("evt-failed").closest("button")!);
    const panel = screen.getByLabelText("감사 이벤트 상세");
    expect(within(panel).getByText("evt-failed")).toBeInTheDocument();
    expect(screen.queryByText("secret-token")).not.toBeInTheDocument();
    expect(screen.queryByText("key-123")).not.toBeInTheDocument();
    expect(screen.queryByText("pk-test")).not.toBeInTheDocument();
    expect(screen.queryByText("mock-id-token")).not.toBeInTheDocument();
  });

  it("shows ResourceRef navigation links", async () => {
    renderPage();
    await screen.findByText("evt-triggered");
    expect(screen.getByRole("link", { name: "발견 사항 보기" })).toHaveAttribute("href", "/investigation");
    expect(screen.getByRole("link", { name: "실행 이력 보기" })).toHaveAttribute("href", "/execution");
    expect(screen.getByRole("link", { name: "조치 계획 보기" })).toHaveAttribute("href", "/remediation");
  });

  it("shows empty state when no events", async () => {
    getAudit = vi.fn(async () => ({
      ...mockResponse,
      events: [],
      summary: { ...mockResponse.summary, total: 0, recent: 0 },
    }));
    renderPage();
    expect(await screen.findByText("현재 기록된 감사 이벤트가 없습니다.")).toBeInTheDocument();
  });
});

describe("AuditPage error states", () => {
  afterEach(() => {
    cleanup();
    getAudit = vi.fn(async () => mockResponse);
  });

  it("shows 401 message", async () => {
    getAudit = vi.fn(async () => {
      throw new ApiError(401, "인증이 필요합니다.");
    });
    renderPage();
    expect(await screen.findByText("인증이 필요합니다.")).toBeInTheDocument();
  });

  it("shows 403 message", async () => {
    getAudit = vi.fn(async () => {
      throw new ApiError(403, "이 작업을 볼 권한이 없습니다.");
    });
    renderPage();
    expect(await screen.findByText("감사 로그 정보를 볼 권한이 없습니다.")).toBeInTheDocument();
  });

  it("shows 500 message and retry", async () => {
    getAudit = vi.fn(async () => {
      throw new ApiError(500, "운영 정보를 불러오지 못했습니다.");
    });
    renderPage();
    expect(await screen.findByText("감사 로그 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("AuditPage loading", () => {
  afterEach(() => {
    cleanup();
    getAudit = vi.fn(async () => mockResponse);
  });

  it("shows loading skeleton before data arrives", async () => {
    getAudit = vi.fn(
      () =>
        new Promise<AuditResponse>((resolve) => {
          setTimeout(() => resolve(mockResponse), 100);
        }),
    );
    renderPage();
    expect(document.querySelector(".investigation-loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("PriceBrain 감사 로그")).toBeInTheDocument());
  });

  it("calls getAudit through operations API", async () => {
    renderPage();
    await screen.findByText("PriceBrain 감사 로그");
    expect(getAudit).toHaveBeenCalled();
  });
});

describe("AuditPage read-only security", () => {
  it("does not expose execute controls", async () => {
    renderPage();
    await screen.findByText("PriceBrain 감사 로그");
    expect(screen.queryByRole("button", { name: /^execute$/i })).not.toBeInTheDocument();
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
