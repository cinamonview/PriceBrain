import type {
  CommandCenterResponse,
  DashboardResponse,
  ExecutionResponse,
  InvestigationResponse,
  RemediationPlanResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function mapApiError(status: number, detail?: string): string {
  if (status === 401) {
    return "인증이 필요합니다.";
  }
  if (status === 403) {
    return "이 작업을 볼 권한이 없습니다.";
  }
  if (status >= 500) {
    return "운영 정보를 불러오지 못했습니다.";
  }
  return detail && !looksLikeSecret(detail) ? detail : "요청을 처리하지 못했습니다.";
}

function looksLikeSecret(value: string): boolean {
  const lowered = value.toLowerCase();
  return (
    lowered.includes("bearer ") ||
    lowered.includes("authorization") ||
    lowered.includes("api_key") ||
    lowered.includes("credential") ||
    lowered.includes("webhook") ||
    value.length > 120
  );
}

async function request<T>(path: string, getToken: () => Promise<string | null>): Promise<T> {
  const token = await getToken();
  if (!token) {
    throw new ApiError(401, mapApiError(401));
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  const body = (await response.json().catch(() => ({}))) as { detail?: string };
  if (!response.ok) {
    throw new ApiError(response.status, mapApiError(response.status, body.detail));
  }
  return body as T;
}

export function createOperationsApi(getToken: () => Promise<string | null>) {
  return {
    getDashboard: () => request<DashboardResponse>("/api/operations/dashboard", getToken),
    getInvestigation: () => request<InvestigationResponse>("/api/operations/investigation", getToken),
    getRemediation: () => request<RemediationPlanResponse>("/api/operations/remediation", getToken),
    getExecution: () => request<ExecutionResponse>("/api/operations/execution", getToken),
    getCommandCenter: () => request<CommandCenterResponse>("/api/operations/command-center", getToken),
  };
}

export type OperationsApi = ReturnType<typeof createOperationsApi>;

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
