import { useState } from "react";
import { login } from "./api";

// Sign-in for installs without the demo button (air-gapped and dev modes). Accounts come from `sutradhar users create`.
export default function Login({ done }: { done: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try { await login(email, password); done(); } catch (err) { setError((err as Error).message); setBusy(false); }
  };
  return (
    <form className="panel" onSubmit={submit} style={{ maxWidth: 420 }}>
      <h2>Sign in</h2>
      <div className="body">
        <label>Email<br /><input required type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%", padding: 8, border: "3px solid #000" }} /></label>
        <label>Password<br /><input required type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%", padding: 8, border: "3px solid #000" }} /></label>
        {error && <p className="err" role="alert">{error}</p>}
        <button className="btn primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </div>
    </form>
  );
}
