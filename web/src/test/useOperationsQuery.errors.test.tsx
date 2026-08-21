import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { ApiError } from "../api/operationsApi";
import { useOperationsQuery } from "../hooks/useOperationsQuery";
import { ConnectionProvider } from "../auth/ConnectionContext";

function wrapper({ children }: { children: React.ReactNode }) {
  return <ConnectionProvider>{children}</ConnectionProvider>;
}

describe("useOperationsQuery error states", () => {
  it("maps 401 to unauthorized message", async () => {
    const fetcher = vi.fn(async () => {
      throw new ApiError(401, "인증이 필요합니다.");
    });
    const { result } = renderHook(
      () => useOperationsQuery({ enabled: true, fetcher, refreshMs: 0 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.status).toBe("unauthorized"));
    expect(result.current.errorMessage).toBe("인증이 필요합니다.");
  });

  it("maps 403 to forbidden message", async () => {
    const fetcher = vi.fn(async () => {
      throw new ApiError(403, "이 작업을 볼 권한이 없습니다.");
    });
    const { result } = renderHook(
      () => useOperationsQuery({ enabled: true, fetcher, refreshMs: 0 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.status).toBe("forbidden"));
    expect(result.current.errorMessage).toBe("이 작업을 볼 권한이 없습니다.");
  });
});
