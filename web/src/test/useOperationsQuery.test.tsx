import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import { act, renderHook } from "@testing-library/react";
import { ConnectionProvider } from "../auth/ConnectionContext";

function wrapper({ children }: { children: React.ReactNode }) {
  return <ConnectionProvider>{children}</ConnectionProvider>;
}

describe("useOperationsQuery", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("cleans up auto refresh timer on unmount", async () => {
    const fetcher = vi.fn(async () => ({ ok: true }));
    const { unmount } = renderHook(
      () =>
        useOperationsQuery({
          enabled: true,
          fetcher,
          refreshMs: 1000,
        }),
      { wrapper },
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(fetcher).toHaveBeenCalledTimes(2);

    unmount();
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not fetch when disabled", async () => {
    const fetcher = vi.fn(async () => ({ ok: true }));
    renderHook(
      () =>
        useOperationsQuery({
          enabled: false,
          fetcher,
          refreshMs: 1000,
        }),
      { wrapper },
    );
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("uses refresh interval from env default", () => {
    expect(getRefreshIntervalMs()).toBeGreaterThanOrEqual(15000);
  });
});
