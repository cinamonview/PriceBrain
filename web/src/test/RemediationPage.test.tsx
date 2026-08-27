import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../api/operationsApi";
import { RemediationPage } from "../pages/RemediationPage";
import { ConnectionProvider } from "../auth/ConnectionContext";
import type { RemediationPlanResponse } from "../api/types";

const mockActions = [
  {
    action_id: "a-high",
    action_type: "REVIEW_RUNNER",
    priority: "HIGH",
    risk: "HIGH",
    finding_id: "f-runner",
    area: "runner",
    title: "Review Runner Cycle",
    reason: "Runner failures require human review",
    recommended_steps: ["Inspect runner logs"],
    preconditions: ["Ops approval required"],
    human_approval_required: true,
    auto_executable: false,
    metadata: { approval_token: "secret-token" },
  },
  {
    action_id: "a-medium",
    action_type: "REVIEW_CRAWLER_TARGET",
    priority: "MEDIUM",
    risk: "MEDIUM",
    finding_id: "f-crawler",
    area: "crawler",
    target_id: "ssg_123",
    alert_id: null,
    title: "Review Crawler Target",
    reason: "Target access denied",
    recommended_steps: [],
    preconditions: [],
    human_approval_required: true,
    auto_executable: false,
    metadata: {},
  },
  {
    action_id: "a-low",
    action_type: "NO_ACTION",
    priority: "LOW",
    risk: "LOW",
    finding_id: "f-info",
    area: "runner",
    title: "No Action Required",
    reason: "Informational only",
    recommended_steps: [],
    preconditions: [],
    human_approval_required: true,
    auto_executable: false,
    metadata: {},
  },
];

const mockResponse: RemediationPlanResponse = {
  generated_at: "2026-08-21T12:00:00Z",
  health: "DEGRADED",
  total_findings: 3,
  actionable_findings: 2,
  read_errors: 0,
  summary: {
    total_actions: 3,
    actionable_actions: 2,
    no_action_count: 1,
    by_priority: { HIGH: 1, MEDIUM: 1, LOW: 1 },
    by_area: { runner: 2, crawler: 1 },
    read_errors: 0,
  },
  actions: mockActions,
};

let getRemediation = vi.fn(async () => mockResponse);

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: {
        getRemediation,
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
        <RemediationPage />
      </ConnectionProvider>
    </MemoryRouter>,
  );
}

describe("RemediationPage", () => {
  afterEach(() => {
    cleanup();
    getRemediation = vi.fn(async () => mockResponse);
  });

  it("renders remediation plan with priorities and policy flags", async () => {
    renderPage();
    expect(await screen.findByText("PriceBrain 조치 계획")).toBeInTheDocument();
    expect(screen.getByText("계획만 생성")).toBeInTheDocument();
    expect(screen.getAllByText("사용자 승인 필요").length).toBeGreaterThan(0);
    expect(screen.getByText("자동 실행 비활성화")).toBeInTheDocument();
    expect(screen.getByText("Review Runner Cycle")).toBeInTheDocument();
    expect(document.querySelector(".summary-count-card.priority-high")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.priority-medium")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.priority-low")).toHaveTextContent("1");
  });

  it("shows human approval required and auto_executable=false on cards", async () => {
    renderPage();
    await screen.findByText("Review Runner Cycle");
    expect(screen.getAllByText("필요").length).toBeGreaterThan(0);
    expect(screen.getAllByText("아니오").length).toBeGreaterThan(0);
  });

  it("filters by priority, area, failures-only, target, alert, and search", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Review Runner Cycle" });

    await user.selectOptions(screen.getByLabelText("우선순위 필터"), "HIGH");
    expect(screen.getByRole("heading", { name: "Review Runner Cycle" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Review Crawler Target" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("우선순위 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("영역 필터"), "crawler");
    expect(screen.getByRole("heading", { name: "Review Crawler Target" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("영역 필터"), "ALL");
    await user.click(screen.getByLabelText("실패 항목만"));
    expect(screen.queryByRole("heading", { name: "No Action Required" })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("실패 항목만"));
    await user.type(screen.getByLabelText("대상 필터"), "ssg_123");
    expect(screen.getByRole("heading", { name: "Review Crawler Target" })).toBeInTheDocument();

    await user.clear(screen.getByLabelText("대상 필터"));
    await user.type(screen.getByLabelText("조치 계획 검색"), "runner cycle");
    expect(screen.getByRole("heading", { name: "Review Runner Cycle" })).toBeInTheDocument();
  });

  it("opens action detail panel and redacts sensitive metadata", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Review Runner Cycle" });
    await user.click(screen.getByRole("button", { name: /Review Runner Cycle/i }));
    const panel = screen.getByLabelText("조치 상세");
    expect(within(panel).getByText("REVIEW_RUNNER")).toBeInTheDocument();
    expect(within(panel).getByText(/Inspect runner logs/)).toBeInTheDocument();
    expect(screen.queryByText("secret-token")).not.toBeInTheDocument();
    expect(screen.queryByText("mock-id-token")).not.toBeInTheDocument();
  });

  it("links to investigation without execute controls", async () => {
    renderPage();
    await screen.findByText("PriceBrain 조치 계획");
    expect(screen.getAllByRole("link", { name: "발견 사항 보기" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /^execute$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve & execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^run$/i })).not.toBeInTheDocument();
  });

  it("shows empty state when no actions", async () => {
    getRemediation = vi.fn(async () => ({
      ...mockResponse,
      actions: [],
      summary: { ...mockResponse.summary, total_actions: 0, actionable_actions: 0 },
    }));
    renderPage();
    expect(await screen.findByText("현재 제안된 조치가 없습니다.")).toBeInTheDocument();
  });
});

describe("RemediationPage error states", () => {
  afterEach(() => {
    cleanup();
    getRemediation = vi.fn(async () => mockResponse);
  });

  it("shows 401 message", async () => {
    getRemediation = vi.fn(async () => {
      throw new ApiError(401, "인증이 필요합니다.");
    });
    renderPage();
    expect(await screen.findByText("인증이 필요합니다.")).toBeInTheDocument();
  });

  it("shows 403 message", async () => {
    getRemediation = vi.fn(async () => {
      throw new ApiError(403, "이 작업을 볼 권한이 없습니다.");
    });
    renderPage();
    expect(await screen.findByText("조치 계획 정보를 볼 권한이 없습니다.")).toBeInTheDocument();
  });

  it("shows 500 message and retry", async () => {
    getRemediation = vi.fn(async () => {
      throw new ApiError(500, "운영 정보를 불러오지 못했습니다.");
    });
    renderPage();
    expect(await screen.findByText("조치 계획 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("RemediationPage loading", () => {
  afterEach(() => {
    cleanup();
    getRemediation = vi.fn(async () => mockResponse);
  });

  it("shows loading skeleton before data arrives", async () => {
    getRemediation = vi.fn(
      () =>
        new Promise<RemediationPlanResponse>((resolve) => {
          setTimeout(() => resolve(mockResponse), 100);
        }),
    );
    renderPage();
    expect(document.querySelector(".investigation-loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("PriceBrain 조치 계획")).toBeInTheDocument());
  });
});

describe("RemediationPage authorization", () => {
  afterEach(() => {
    cleanup();
    getRemediation = vi.fn(async () => mockResponse);
  });

  it("calls getRemediation through operations API", async () => {
    renderPage();
    await screen.findByText("PriceBrain 조치 계획");
    expect(getRemediation).toHaveBeenCalled();
  });
});
