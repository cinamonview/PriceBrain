import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { ConnectionProvider } from "../auth/ConnectionContext";

const mockUser = {
  uid: "viewer-1",
  email: "viewer@example.com",
  roles: ["OPS_VIEWER"] as const,
};

vi.mock("../firebase", () => ({
  isFirebaseConfigured: () => true,
  getFirebaseAuth: () => ({}),
}));

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: (_auth: unknown, callback: (user: unknown) => void) => {
    callback(null);
    return () => undefined;
  },
  signInWithEmailAndPassword: vi.fn(async () => ({
    user: {
      uid: mockUser.uid,
      email: mockUser.email,
      getIdToken: async () => "mock-id-token",
      getIdTokenResult: async () => ({ claims: { ops_roles: ["OPS_VIEWER"] } }),
    },
  })),
  signOut: vi.fn(async () => undefined),
}));

function renderApp() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <ConnectionProvider>
          <App />
        </ConnectionProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("App shell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders login screen", () => {
    renderApp();
    expect(screen.getByText("PriceBrain 운영")).toBeInTheDocument();
  });

  it("does not render token in UI after login attempt", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByLabelText("이메일"), "viewer@example.com");
    await user.type(screen.getByLabelText("비밀번호"), "password");
    await user.click(screen.getByRole("button", { name: "로그인" }));

    await waitFor(() => {
      expect(screen.queryByText("mock-id-token")).not.toBeInTheDocument();
    });
  });
});
