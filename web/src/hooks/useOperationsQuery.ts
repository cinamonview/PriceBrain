import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/operationsApi";
import type { QueryStatus } from "../api/types";
import { useConnectionStatus, type ConnectionStatus } from "../auth/ConnectionContext";

interface UseOperationsQueryOptions<T> {
  enabled: boolean;
  fetcher: () => Promise<T>;
  refreshMs?: number;
}

interface UseOperationsQueryResult<T> {
  data: T | null;
  status: QueryStatus;
  errorMessage: string | null;
  refresh: () => Promise<void>;
}

export function useOperationsQuery<T>({
  enabled,
  fetcher,
  refreshMs = 45000,
}: UseOperationsQueryOptions<T>): UseOperationsQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<QueryStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inFlightRef = useRef(false);
  const fetcherRef = useRef(fetcher);

  fetcherRef.current = fetcher;
  const { setStatus: setConnectionStatus } = useConnectionStatus();

  const updateConnectionStatus = useCallback((queryStatus: QueryStatus) => {
    const mapped: ConnectionStatus =
      queryStatus === "success"
        ? "connected"
        : queryStatus === "unauthorized" || queryStatus === "forbidden"
          ? "degraded"
          : queryStatus === "error"
            ? "error"
            : "unknown";
    setConnectionStatus(mapped);
  }, [setConnectionStatus]);

  const refresh = useCallback(async () => {
    if (!enabled || inFlightRef.current) {
      return;
    }
    inFlightRef.current = true;
    setStatus((current) => (current === "success" ? current : "loading"));
    try {
      const result = await fetcherRef.current();
      setData(result);
      setStatus("success");
      setErrorMessage(null);
      updateConnectionStatus("success");
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) {
          setStatus("unauthorized");
          updateConnectionStatus("unauthorized");
        } else if (error.status === 403) {
          setStatus("forbidden");
          updateConnectionStatus("forbidden");
        } else {
          setStatus("error");
          updateConnectionStatus("error");
        }
        setErrorMessage(error.message);
      } else {
        setStatus("error");
        setErrorMessage("운영 정보를 불러오지 못했습니다.");
        updateConnectionStatus("error");
      }
    } finally {
      inFlightRef.current = false;
    }
  }, [enabled, updateConnectionStatus]);

  useEffect(() => {
    if (!enabled) {
      setStatus("idle");
      return;
    }
    void refresh();
  }, [enabled, refresh]);

  useEffect(() => {
    if (!enabled || refreshMs <= 0) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, refreshMs);
    return () => window.clearInterval(timer);
  }, [enabled, refresh, refreshMs]);

  return { data, status, errorMessage, refresh };
}

export function getRefreshIntervalMs(): number {
  const raw = import.meta.env.VITE_OPERATIONS_REFRESH_MS;
  const parsed = raw ? Number(raw) : 45000;
  return Number.isFinite(parsed) && parsed >= 15000 ? parsed : 45000;
}
