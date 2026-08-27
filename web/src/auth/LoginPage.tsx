import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { UI } from "../utils/uiLabels";

export function LoginPage() {
  const navigate = useNavigate();
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
      navigate("/", { replace: true });
    } catch {
      setError("이메일 또는 비밀번호가 올바르지 않습니다. Firebase 계정과 role claim을 확인하세요.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!configured) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>{UI.operationsTitle}</h1>
          <p>Firebase 웹 설정이 없습니다.</p>
          <p>`web/.env.example`을 `web/.env.local`로 복사한 뒤 값을 설정하세요.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={(event) => void handleSubmit(event)}>
        <h1>{UI.operationsTitle}</h1>
        <p>Firebase Authentication으로 로그인합니다.</p>
        <label>
          {UI.email}
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          {UI.password}
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
          {submitting ? UI.signingIn : UI.signIn}
        </button>
      </form>
    </div>
  );
}
