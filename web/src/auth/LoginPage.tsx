import { FormEvent, useState } from "react";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { login, configured } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
    } catch {
      setError("로그인에 실패했습니다. Firebase 계정과 role claim을 확인하세요.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!configured) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>PriceBrain Operations</h1>
          <p>Firebase web configuration is missing.</p>
          <p>Copy `web/.env.example` to `web/.env.local` and set placeholder values.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={(event) => void handleSubmit(event)}>
        <h1>PriceBrain Operations</h1>
        <p>Firebase Authentication으로 로그인합니다.</p>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error ? <div className="query-state error">{error}</div> : null}
        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
