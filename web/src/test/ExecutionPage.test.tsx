import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { ApiError } from "../api/operationsApi";
import { ExecutionPage } from "../pages/ExecutionPage";
import { ConnectionProvider } from "../auth/ConnectionContext";
import type { ExecutionHistoryEntry, ExecutionResponse } from "../api/types";

function makeEntry(
  overrides: Partial<ExecutionHistoryEntry> & Pick<ExecutionHistoryEntry, "execution_id" | "status">,
): ExecutionHistoryEntry {
  return {
    action_id: "a-default",
    action_type: "REVIEW_RUNNER",
    mode: "PLAN",
    priority: "MEDIUM",
    risk: "MEDIUM",
    area: "runner",
    title: "Execution title",
    message: "Execution message",
    mutation_performed: false,
    approval_verified: false,
    metadata: {},
    ...overrides,
  };
}

const mockEntries = [
  makeEntry({
    execution_id: "exec-planned",
    status: "PLANNED",
    mode: "PLAN",
    occurred_at: "2026-08-21T08:00:00Z",
  }),
  makeEntry({
    execution_id: "exec-dry-run",
    status: "DRY_RUN",
    mode: "DRY_RUN",
    occurred_at: "2026-08-21T09:00:00Z",
  }),
  makeEntry({
    execution_id: "exec-executed",
    status: "EXECUTED",
    mode: "EXECUTE",
    mutation_performed: true,
    approval_verified: true,
    occurred_at: "2026-08-21T10:00:00Z",
  }),
  makeEntry({
    execution_id: "exec-blocked",
    status: "BLOCKED",
    mode: "EXECUTE",
    area: "crawler",
    target_id: "ssg_123",
    alert_id: "alert-1",
    occurred_at: "2026-08-21T11:00:00Z",
  }),
  makeEntry({
    execution_id: "exec-failed",
    status: "FAILED",
    mode: "EXECUTE",
    error_code: "EXECUTION_FAILED",
    message: "Execution failed",
    metadata: { approval_token: "secret-token", finding_id: "finding-1" },
    occurred_at: "2026-08-21T12:00:00Z",
  }),
];

const mockResponse: ExecutionResponse = {
  generated_at: "2026-08-21T12:30:00Z",
  health: "DEGRADED",
  health_reasons: ["recent failures"],
  summary: {
    total: 5,
    planned: 1,
    dry_run: 1,
    approved: 0,
    executed: 1,
    blocked: 1,
    failed: 1,
    skipped: 0,
    mutation_count: 1,
    approval_failures: 1,
    recent_failures: 1,
    by_action_type: {},
    by_area: {},
    read_errors: 0,
  },
  entries: mockEntries.map((entry) => ({ entry })),
};

let getExecution = vi.fn(async () => mockResponse);

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: {
        getExecution,
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
        <ExecutionPage />
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

describe("ExecutionPage", () => {
  afterEach(() => {
    cleanup();
    getExecution = vi.fn(async () => mockResponse);
  });

  it("renders execution history with health and status summaries", async () => {
    renderPage();
    expect(await screen.findByText("PriceBrain 실행 이력")).toBeInTheDocument();
    expect(screen.getByText("실행 상태")).toBeInTheDocument();
    expect(screen.getAllByText("일부 문제").length).toBeGreaterThan(0);
    expect(document.querySelector(".summary-count-card.execution-status-planned")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.execution-status-dry_run")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.execution-status-executed")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.execution-status-blocked")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.execution-status-failed")).toHaveTextContent("1");
    expect(screen.getAllByText("계획됨").length).toBeGreaterThan(0);
    expect(screen.getAllByText("시험 실행").length).toBeGreaterThan(0);
    expect(screen.getAllByText("실행 완료").length).toBeGreaterThan(0);
    expect(screen.getAllByText("차단됨").length).toBeGreaterThan(0);
    expect(screen.getAllByText("실패").length).toBeGreaterThan(0);
  });

  it.each([
    ["HEALTHY", "HEALTHY"],
    ["CRITICAL", "CRITICAL"],
    ["UNKNOWN", "UNKNOWN"],
  ] as const)("renders execution health %s", async (health, label) => {
    getExecution = vi.fn(async () => ({ ...mockResponse, health }));
    renderPage();
    const expectedLabel =
      label === "HEALTHY"
        ? "정상"
        : label === "CRITICAL"
          ? "치명적"
          : "확인 불가";
    expect(await screen.findAllByText(expectedLabel)).not.toHaveLength(0);
  });

  it("filters by status, mode, area, target, alert, failures-only, search, and sort", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("exec-failed");

    await user.selectOptions(screen.getByLabelText("상태 필터"), "FAILED");
    expect(screen.getByText("exec-failed")).toBeInTheDocument();
    expect(screen.queryByText("exec-planned")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("상태 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("실행 모드 필터"), "PLAN");
    expect(screen.getByText("exec-planned")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("실행 모드 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("영역 필터"), "crawler");
    expect(screen.getByText("exec-blocked")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("영역 필터"), "ALL");
    await user.type(screen.getByLabelText("대상 필터"), "ssg_123");
    expect(screen.getByText("exec-blocked")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("대상 필터"));
    await user.type(screen.getByLabelText("알림 필터"), "alert-1");
    expect(screen.getByText("exec-blocked")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("알림 필터"));
    await user.click(screen.getByLabelText("실패 항목만"));
    expect(screen.getByText("exec-failed")).toBeInTheDocument();
    expect(screen.queryByText("exec-blocked")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("실패 항목만"));
    await user.type(screen.getByLabelText("실행 이력 검색"), "dry-run");
    expect(screen.getByText("exec-dry-run")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("실행 이력 검색"));
    await user.selectOptions(screen.getByLabelText("정렬 순서"), "OLDEST");
    expect(screen.getByText("exec-planned")).toBeInTheDocument();
  });

  it("opens execution detail panel and redacts sensitive metadata", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("exec-failed");
    const card = screen.getByText("exec-failed").closest("button");
    expect(card).toBeTruthy();
    await user.click(card!);
    const panel = screen.getByLabelText("실행 이력 상세");
    expect(within(panel).getByText("exec-failed")).toBeInTheDocument();
    expect(within(panel).getByText("EXECUTION_FAILED")).toBeInTheDocument();
    expect(screen.queryByText("secret-token")).not.toBeInTheDocument();
    expect(screen.queryByText("mock-id-token")).not.toBeInTheDocument();
  });

  it("shows empty state when no entries", async () => {
    getExecution = vi.fn(async () => ({
      ...mockResponse,
      entries: [],
      summary: { ...mockResponse.summary, total: 0, planned: 0, dry_run: 0, executed: 0, blocked: 0, failed: 0 },
    }));
    renderPage();
    expect(await screen.findByText("현재 기록된 실행 이력이 없습니다.")).toBeInTheDocument();
  });
});

describe("ExecutionPage error states", () => {
  afterEach(() => {
    cleanup();
    getExecution = vi.fn(async () => mockResponse);
  });

  it("shows 401 message", async () => {
    getExecution = vi.fn(async () => {
      throw new ApiError(401, "인증이 필요합니다.");
    });
    renderPage();
    expect(await screen.findByText("인증이 필요합니다.")).toBeInTheDocument();
  });

  it("shows 403 message", async () => {
    getExecution = vi.fn(async () => {
      throw new ApiError(403, "이 작업을 볼 권한이 없습니다.");
    });
    renderPage();
    expect(await screen.findByText("실행 이력 정보를 볼 권한이 없습니다.")).toBeInTheDocument();
  });

  it("shows 500 message and retry", async () => {
    getExecution = vi.fn(async () => {
      throw new ApiError(500, "운영 정보를 불러오지 못했습니다.");
    });
    renderPage();
    expect(await screen.findByText("실행 이력 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("ExecutionPage loading and authorization", () => {
  afterEach(() => {
    cleanup();
    getExecution = vi.fn(async () => mockResponse);
  });

  it("shows loading skeleton before data arrives", async () => {
    getExecution = vi.fn(
      () =>
        new Promise<ExecutionResponse>((resolve) => {
          setTimeout(() => resolve(mockResponse), 100);
        }),
    );
    renderPage();
    expect(document.querySelector(".investigation-loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("PriceBrain 실행 이력")).toBeInTheDocument());
  });

  it("calls getExecution through operations API", async () => {
    renderPage();
    await screen.findByText("PriceBrain 실행 이력");
    expect(getExecution).toHaveBeenCalled();
  });
});

describe("ExecutionPage read-only security", () => {
  it("does not expose execute controls", async () => {
    renderPage();
    await screen.findByText("PriceBrain 실행 이력");
    expect(screen.queryByRole("button", { name: /^execute$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve & execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^run$/i })).not.toBeInTheDocument();
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
