import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";

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

describe("App shell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders login screen", () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("PriceBrain Operations")).toBeInTheDocument();
  });

  it("does not render token in UI after login attempt", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText("Email"), "viewer@example.com");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.queryByText("mock-id-token")).not.toBeInTheDocument();
    });
  });
});