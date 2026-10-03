import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { errorMessage } from "../api";
import { useAuth } from "../auth";
import { Alert, Button, Field } from "../ui";

const TRACKS: [number, number][][] = [
  [[2, 14], [20, 9], [33, 20], [58, 11], [74, 16]],
  [[8, 22], [34, 7], [45, 13], [64, 24]],
  [[4, 10], [18, 18], [41, 9], [55, 15], [76, 12]],
  [[12, 16], [32, 21], [62, 8], [74, 18]],
  [[6, 12], [22, 14], [42, 15], [67, 10], [81, 9]],
];
const PLAYHEAD = 60;
const toX = (value: number) => 7 + value * 0.9;

/** Clip state relative to the playhead: recorded, being recorded now, or still to come. */
function clipState(start: number, width: number): string {
  if (start + width <= PLAYHEAD) return "recorded";
  return start >= PLAYHEAD ? "ahead" : "live";
}

/**
 * Robots being recorded over time: one track per robot, clips for episodes and
 * a playhead marking now. Clips behind it are recorded, a clip under it is
 * being recorded, and clips after it are still to come.
 */
function EpisodeArt() {
  return (
    <svg className="art" viewBox="0 0 100 64" aria-hidden="true">
      {TRACKS.map((clips, row) => {
        const y = 8 + row * 12;
        const live = clips.some(([start, width]) => clipState(start, width) === "live");
        return (
          <g key={row}>
            <line className="track" x1="7" x2="98" y1={y} y2={y} />
            <circle className={live ? "track-dot track-dot--live" : "track-dot"} cx="2.5" cy={y} r="1.3" />
            {clips.map(([start, width], index) => (
              <rect
                key={start}
                x={toX(start)}
                y={y - 2.5}
                width={width * 0.9}
                height="5"
                rx="1.2"
                className={`clip clip--${clipState(start, width)} clip--tone${(row + index) % 3}`}
              />
            ))}
          </g>
        );
      })}
      <line className="playhead" x1={toX(PLAYHEAD)} x2={toX(PLAYHEAD)} y1="1.5" y2="62.5" />
      <rect className="playhead__knob" x={toX(PLAYHEAD) - 1.4} y="0" width="2.8" height="2.8" rx="0.6" />
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
