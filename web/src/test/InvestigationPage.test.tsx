import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { within } from "@testing-library/react";
import { ApiError } from "../api/operationsApi";
import { InvestigationPage } from "../pages/InvestigationPage";
import { ConnectionProvider } from "../auth/ConnectionContext";
import type { InvestigationResponse } from "../api/types";

const mockFindings = [
  {
    finding_id: "f-critical",
    severity: "CRITICAL",
    area: "runner",
    code: "RUNNER_CYCLE_FAILURE",
    title: "Runner Cycle Failure Repeated",
    message: "최근 Runner cycle이 반복적으로 실패했습니다.",
    target_id: "target-1",
    alert_id: null,
    event_id: null,
    occurred_at: "2026-08-21T10:00:00Z",
    metadata: { retry_count: 3, approval_token: "hidden" },
  },
  {
    finding_id: "f-error",
    severity: "ERROR",
    area: "crawler",
    code: "CRAWLER_READ_ERROR",
    title: "Crawler Read Error",
    message: "Crawler read failed",
    target_id: "ssg_123",
    alert_id: null,
    event_id: null,
    occurred_at: "2026-08-21T09:00:00Z",
    metadata: {},
  },
  {
    finding_id: "f-warning",
    severity: "WARNING",
    area: "crawler",
    code: "CRAWLER_ACCESS_DENIED",
    title: "Crawler Access Denied",
    message: "SSG 접근이 거부되었습니다.",
    target_id: "ssg_456",
    alert_id: null,
    event_id: null,
    occurred_at: "2026-08-21T08:00:00Z",
    metadata: {},
  },
  {
    finding_id: "f-info",
    severity: "INFO",
    area: "runner",
    code: "RUNNER_OK",
    title: "Runner Healthy",
    message: "Runner cycle succeeded",
    target_id: null,
    alert_id: "alert-1",
    event_id: null,
    occurred_at: "2026-08-21T07:00:00Z",
    metadata: {},
  },
];

const mockResponse: InvestigationResponse = {
  generated_at: "2026-08-21T12:00:00Z",
  health: "DEGRADED",
  summary: {
    total_findings: 4,
    critical_count: 1,
    error_count: 1,
    warning_count: 1,
    info_count: 1,
    areas: { runner: 2, crawler: 2 },
    read_errors: 0,
  },
  findings: mockFindings,
  dashboard_summary: { health: "DEGRADED", reasons: [] },
  crawler: {},
  price: {},
  alerts: {},
  notifications: {},
  runner: {},
  audit: {},
};

let getInvestigation = vi.fn(async () => mockResponse);

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: {
        getInvestigation,
      },
      login: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(async () => "mock-id-token"),
    }),
  };
});

function renderPage() {
  return render(
    <ConnectionProvider>
      <InvestigationPage />
    </ConnectionProvider>,
  );
}

describe("InvestigationPage", () => {
  afterEach(() => {
    cleanup();
    getInvestigation = vi.fn(async () => mockResponse);
  });

  it("renders investigation page with health and findings", async () => {
    renderPage();
    expect(await screen.findByText("PriceBrain 조사")).toBeInTheDocument();
    expect(screen.getByText("조사 상태")).toBeInTheDocument();
    expect(screen.getAllByText("일부 문제").length).toBeGreaterThan(0);
    expect(screen.getByText("실행기 주기 실패 반복")).toBeInTheDocument();
    expect(screen.getByText("크롤러 읽기 오류")).toBeInTheDocument();
    expect(screen.getByText("크롤러 접근 거부")).toBeInTheDocument();
    expect(screen.getByText("실행기 정상")).toBeInTheDocument();
  });

  it("renders severity summary cards from contract", async () => {
    renderPage();
    await screen.findByText("PriceBrain 조사");
    expect(document.querySelector(".summary-count-card.severity-critical")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.severity-error")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.severity-warning")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.severity-info")).toHaveTextContent("1");
  });

  it("filters findings by severity, area, failures-only, target, alert", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "실행기 주기 실패 반복" });

    await user.selectOptions(screen.getByLabelText("심각도 필터"), "CRITICAL");
    expect(screen.getByRole("heading", { name: "실행기 주기 실패 반복" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "크롤러 읽기 오류" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("심각도 필터"), "ALL");
    await user.selectOptions(screen.getByLabelText("영역 필터"), "crawler");
    expect(screen.getByRole("heading", { name: "크롤러 읽기 오류" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "실행기 주기 실패 반복" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("영역 필터"), "ALL");
    await user.click(screen.getByLabelText("실패 항목만"));
    expect(screen.queryByRole("heading", { name: "실행기 정상" })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("실패 항목만"));
    await user.type(screen.getByLabelText("대상 필터"), "ssg_123");
    expect(screen.getByRole("heading", { name: "크롤러 읽기 오류" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "크롤러 접근 거부" })).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText("대상 필터"));
    await user.type(screen.getByLabelText("알림 필터"), "alert-1");
    expect(screen.getByRole("heading", { name: "실행기 정상" })).toBeInTheDocument();
  });

  it("opens finding detail and redacts metadata secrets", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "실행기 주기 실패 반복" });
    await user.click(screen.getByRole("button", { name: /실행기 주기 실패 반복/i }));
    const panel = screen.getByLabelText("발견 사항 상세");
    expect(within(panel).getByText("RUNNER_CYCLE_FAILURE")).toBeInTheDocument();
    expect(within(panel).getByText(/retry_count/i)).toBeInTheDocument();
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
    expect(screen.queryByText("mock-id-token")).not.toBeInTheDocument();
  });

  it("shows empty state when no findings", async () => {
    getInvestigation = vi.fn(async () => ({
      ...mockResponse,
      findings: [],
      summary: {
        ...mockResponse.summary,
        total_findings: 0,
        critical_count: 0,
        error_count: 0,
        warning_count: 0,
        info_count: 0,
      },
    }));
    renderPage();
    expect(await screen.findByText("현재 확인이 필요한 운영 이슈가 없습니다.")).toBeInTheDocument();
  });

  it("does not expose execute controls", async () => {
    renderPage();
    await screen.findByText("PriceBrain 조사");
    expect(screen.queryByRole("button", { name: /^execute$/i })).not.toBeInTheDocument();
  });
});

describe("InvestigationPage error states", () => {
  afterEach(() => {
    cleanup();
    getInvestigation = vi.fn(async () => mockResponse);
  });
  it("shows 401 message", async () => {
    getInvestigation = vi.fn(async () => {
      throw new ApiError(401, "인증이 필요합니다.");
    });
    renderPage();
    expect(await screen.findByText("인증이 필요합니다.")).toBeInTheDocument();
  });

  it("shows 403 message", async () => {
    getInvestigation = vi.fn(async () => {
      throw new ApiError(403, "이 작업을 볼 권한이 없습니다.");
    });
    renderPage();
    expect(await screen.findByText("조사 정보를 볼 권한이 없습니다.")).toBeInTheDocument();
  });

  it("shows 500 message and retry", async () => {
    getInvestigation = vi.fn(async () => {
      throw new ApiError(500, "운영 정보를 불러오지 못했습니다.");
    });
    renderPage();
    expect(await screen.findByText("조사 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("InvestigationPage loading", () => {
  afterEach(() => {
    cleanup();
    getInvestigation = vi.fn(async () => mockResponse);
  });
  it("shows loading skeleton before data arrives", async () => {
    getInvestigation = vi.fn(
      () =>
        new Promise<InvestigationResponse>((resolve) => {
          setTimeout(() => resolve(mockResponse), 100);
        }),
    );
    renderPage();
    expect(document.querySelector(".investigation-loading")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getAllByText("PriceBrain 조사").length).toBeGreaterThan(0),
    );
  });
});
