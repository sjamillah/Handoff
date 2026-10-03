import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { errorMessage } from "../api";
import { useAuth } from "../auth";
import { Alert, Button, Field } from "../ui";

const TRACKS: [string, [number, number][]][] = [
  ["arm-01", [[2, 14], [20, 9], [33, 20], [58, 11], [74, 16]]],
  ["arm-02", [[8, 22], [34, 7], [45, 13], [64, 24]]],
  ["arm-03", [[4, 10], [18, 18], [41, 9], [55, 15], [76, 12]]],
  ["mobile-01", [[12, 16], [32, 21], [60, 8], [72, 18]]],
  ["humanoid-01", [[6, 12], [22, 14], [42, 19], [67, 10], [81, 9]]],
];

/** Recorded episodes drawn as clips on one timeline per robot. */
function EpisodeArt() {
  return (
    <svg className="art" viewBox="0 0 100 62" aria-hidden="true">
      {TRACKS.map(([robot, clips], row) => (
        <g key={robot} transform={`translate(0 ${row * 12})`}>
          <text x="0" y="3.2">
            {robot}
          </text>
          <line x1="0" x2="100" y1="8" y2="8" />
          {clips.map(([x, width], index) => (
            <rect key={x} x={x} y="5.5" width={width} height="5" rx="1.2" className={`clip clip--${(row + index) % 4}`} />
          ))}
        </g>
      ))}
    </svg>
  );
}

/** Sign-in screen: the episode timeline on one side, the form on the other. */
export function Login() {
  const { user, signIn } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await signIn(String(form.get("email")), String(form.get("password")));
    } catch (caught) {
      setError(errorMessage(caught));
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <aside className="login__art">
        <span className="brand">Handoff</span>
        <EpisodeArt />
        <p>Robot episodes, from recording to delivery.</p>
      </aside>
      <section className="login__panel">
        <form className="login__form" onSubmit={submit}>
          <h1>Sign in</h1>
          {error && <Alert error>{error}</Alert>}
          <Field id="email" label="Email">
            <input id="email" name="email" type="email" autoComplete="username" required />
          </Field>
          <Field id="password" label="Password">
            <input id="password" name="password" type="password" autoComplete="current-password" required />
          </Field>
          <Button type="submit" loading={busy}>
            Sign in
          </Button>
          <p className="muted small">Accounts are created by an administrator.</p>
        </form>
      </section>
    </main>
  );
}
