import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { createOperationsApi, getApiBaseUrl, mapApiError } from "../api/operationsApi";

describe("operationsApi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("includes Authorization bearer token", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ generated_at: "t", summary: { health: "HEALTHY", reasons: [] } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const api = createOperationsApi(async () => "secret-test-token");
    await api.getDashboard();

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.headers).toMatchObject({
      Authorization: "Bearer secret-test-token",
    });
  });

  it("maps 401/403/500 errors without leaking secrets", () => {
    expect(mapApiError(401)).toBe("인증이 필요합니다.");
    expect(mapApiError(403)).toBe("이 작업을 볼 권한이 없습니다.");
    expect(mapApiError(500)).toBe("운영 정보를 불러오지 못했습니다.");
    expect(mapApiError(401, "Bearer leaked-token")).toBe("인증이 필요합니다.");
  });

  it("uses env-based API base URL", () => {
    expect(typeof getApiBaseUrl()).toBe("string");
  });
});
