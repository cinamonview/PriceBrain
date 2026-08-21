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
    expect(await screen.findByText("PriceBrain Investigation")).toBeInTheDocument();
    expect(screen.getByText("Investigation Health")).toBeInTheDocument();
    expect(screen.getAllByText("DEGRADED").length).toBeGreaterThan(0);
    expect(screen.getByText("Runner Cycle Failure Repeated")).toBeInTheDocument();
    expect(screen.getByText("Crawler Read Error")).toBeInTheDocument();
    expect(screen.getByText("Crawler Access Denied")).toBeInTheDocument();
    expect(screen.getByText("Runner Healthy")).toBeInTheDocument();
  });

  it("renders severity summary cards from contract", async () => {
    renderPage();
    await screen.findByText("PriceBrain Investigation");
    expect(document.querySelector(".summary-count-card.severity-critical")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.severity-error")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.severity-warning")).toHaveTextContent("1");
    expect(document.querySelector(".summary-count-card.severity-info")).toHaveTextContent("1");
  });

  it("filters findings by severity, area, failures-only, target, alert", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Runner Cycle Failure Repeated" });

    await user.selectOptions(screen.getByLabelText("Severity filter"), "CRITICAL");
    expect(screen.getByRole("heading", { name: "Runner Cycle Failure Repeated" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Crawler Read Error" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Severity filter"), "ALL");
    await user.selectOptions(screen.getByLabelText("Area filter"), "crawler");
    expect(screen.getByRole("heading", { name: "Crawler Read Error" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Runner Cycle Failure Repeated" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Area filter"), "ALL");
    await user.click(screen.getByLabelText("failures only"));
    expect(screen.queryByRole("heading", { name: "Runner Healthy" })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("failures only"));
    await user.type(screen.getByLabelText("Target filter"), "ssg_123");
    expect(screen.getByRole("heading", { name: "Crawler Read Error" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Crawler Access Denied" })).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText("Target filter"));
    await user.type(screen.getByLabelText("Alert filter"), "alert-1");
    expect(screen.getByRole("heading", { name: "Runner Healthy" })).toBeInTheDocument();
  });

  it("opens finding detail and redacts metadata secrets", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Runner Cycle Failure Repeated" });
    await user.click(screen.getByRole("button", { name: /Runner Cycle Failure Repeated/i }));
    const panel = screen.getByLabelText("Finding detail");
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
    await screen.findByText("PriceBrain Investigation");
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
    expect(await screen.findByText("Investigation 정보를 볼 권한이 없습니다.")).toBeInTheDocument();
  });

  it("shows 500 message and retry", async () => {
    getInvestigation = vi.fn(async () => {
      throw new ApiError(500, "운영 정보를 불러오지 못했습니다.");
    });
    renderPage();
    expect(await screen.findByText("Investigation 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
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
      expect(screen.getAllByText("PriceBrain Investigation").length).toBeGreaterThan(0),
    );
  });
});
