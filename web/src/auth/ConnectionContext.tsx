import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type ConnectionStatus = "unknown" | "connected" | "degraded" | "error";

interface ConnectionContextValue {
  status: ConnectionStatus;
  setStatus: (status: ConnectionStatus) => void;
}

const ConnectionContext = createContext<ConnectionContextValue | undefined>(undefined);

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>("unknown");
  const value = useMemo(() => ({ status, setStatus }), [status]);
  return <ConnectionContext.Provider value={value}>{children}</ConnectionContext.Provider>;
}

export function useConnectionStatus(): ConnectionContextValue {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error("useConnectionStatus must be used within ConnectionProvider");
  }
  return context;
}

export function connectionLabel(status: ConnectionStatus): string {
  switch (status) {
    case "connected":
      return "Connected";
    case "degraded":
      return "Auth required";
    case "error":
      return "Unavailable";
    default:
      return "Checking...";
  }
}
