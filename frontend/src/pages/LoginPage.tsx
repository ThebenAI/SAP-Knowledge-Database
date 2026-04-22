import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import type { User } from "../types/api";

type LoginPageProps = {
  onLoginSuccess: (token: string, user: User) => void;
};

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await login({ username, password });
      onLoginSuccess(response.access_token, response.user);
      navigate("/import", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login fehlgeschlagen.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="page">
      <section className="card auth-card">
        <h2>Anmeldung</h2>
        <p>Bitte mit einem berechtigten Benutzerkonto anmelden.</p>
        <form className="auth-form" onSubmit={onSubmit}>
          <label>
            Benutzername
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
          </label>
          <label>
            Passwort
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Anmelden..." : "Anmelden"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>
    </main>
  );
}
