import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import type { OpsRole } from "../api/types";
import { createOperationsApi, type OperationsApi } from "../api/operationsApi";
import { getFirebaseAuth, isFirebaseConfigured } from "../firebase";
import { formatRoleLabel } from "../utils/uiLabels";

export interface AuthUser {
  uid: string;
  email: string | null;
  roles: OpsRole[];
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  configured: boolean;
  operationsApi: OperationsApi;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function parseRoles(claims: Record<string, unknown>): OpsRole[] {
  const raw = claims.ops_roles ?? claims.roles;
  const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
  const allowed: OpsRole[] = ["OPS_VIEWER", "OPS_OPERATOR", "OPS_ADMIN"];
  return values
    .map((item) => String(item).toUpperCase())
    .filter((item): item is OpsRole => allowed.includes(item as OpsRole));
}

async function toAuthUser(user: User): Promise<AuthUser> {
  const tokenResult = await user.getIdTokenResult();
  return {
    uid: user.uid,
    email: user.email,
    roles: parseRoles(tokenResult.claims as Record<string, unknown>),
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = isFirebaseConfigured();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(configured);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!configured) {
      return null;
    }
    const auth = getFirebaseAuth();
    const current = auth.currentUser;
    if (!current) {
      return null;
    }
    return current.getIdToken();
  }, [configured]);

  const operationsApi = useMemo(() => createOperationsApi(getAccessToken), [getAccessToken]);

  useEffect(() => {
    if (!configured) {
      setLoading(false);
      return;
    }
    const auth = getFirebaseAuth();
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (!firebaseUser) {
        setUser(null);
        setLoading(false);
        return;
      }
      setUser(await toAuthUser(firebaseUser));
      setLoading(false);
    });
    return unsubscribe;
  }, [configured]);

  const login = useCallback(async (email: string, password: string) => {
    const auth = getFirebaseAuth();
    const credential = await signInWithEmailAndPassword(auth, email, password);
    setUser(await toAuthUser(credential.user));
  }, []);

  const logout = useCallback(async () => {
    const auth = getFirebaseAuth();
    await signOut(auth);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      configured,
      operationsApi,
      login,
      logout,
      getAccessToken,
    }),
    [user, loading, configured, operationsApi, login, logout, getAccessToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

export function formatPrimaryRole(roles: OpsRole[]): string {
  if (roles.includes("OPS_ADMIN")) {
    return formatRoleLabel("OPS_ADMIN");
  }
  if (roles.includes("OPS_OPERATOR")) {
    return formatRoleLabel("OPS_OPERATOR");
  }
  if (roles.includes("OPS_VIEWER")) {
    return formatRoleLabel("OPS_VIEWER");
  }
  return formatRoleLabel("NO_ROLE");
}
