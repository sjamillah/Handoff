import type { ButtonHTMLAttributes, ReactNode } from "react";

import type { DatasetRequest, RequestStatus } from "./api";
import { ACTION, STATUS } from "./format";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "plain" | "danger";
  loading?: boolean;
}

/** Button with a loading state that blocks repeat clicks. */
export function Button({ variant = "primary", loading, disabled, className = "", ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      className={`button button--${variant} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading}
      {...rest}
    />
  );
}

/** Status shown as text with a small mark, never by colour alone. */
export function StatusBadge({ status }: { status: RequestStatus }) {
  return <span className={`status status--${status}`}>{STATUS[status]}</span>;
}

/** Message box. Errors are announced to screen readers straight away. */
export function Alert({ error, children }: { error?: boolean; children: ReactNode }) {
  return (
    <p className={error ? "alert alert--error" : "alert"} role={error ? "alert" : "status"}>
      {children}
    </p>
  );
}

/** Label, control and error message for one form field. */
export function Field({ id, label, error, children }: { id: string; label: string; error?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error && (
        <span className="field__error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
  );
}

/** Assigned against requested episodes, as the server reports them. */
export function Progress({ request }: { request: DatasetRequest }) {
  return (
    <span className="progress">
      <progress value={request.assigned_count} max={request.episodes_requested} />
      {request.assigned_count}/{request.episodes_requested}
    </span>
  );
}

/** One button per status the server lists as available for this request and user. */
export function Moves({ request, busy, onMove }: { request: DatasetRequest; busy: string | null; onMove: (to: RequestStatus) => void }) {
  return request.available_transitions.map((to) => (
    <Button
      key={to}
      variant={to === "rejected" ? "danger" : "primary"}
      loading={busy === `${request.id}:${to}`}
      disabled={busy !== null}
      onClick={() => onMove(to)}
    >
      {ACTION[to]}
    </Button>
  ));
}

/** Dark band behind a page title. The page content below overlaps its lower edge. */
export function Band({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <section className="band">
      <div className="band__inner">
        <h1>{title}</h1>
        {children}
      </div>
    </section>
  );
}

const STEPS: RequestStatus[] = ["submitted", "in_progress", "delivered", "accepted"];

/** The request's place in the workflow, drawn from the status the server reports. */
export function Steps({ status }: { status: RequestStatus }) {
  const current = STEPS.indexOf(status === "rejected" ? "delivered" : status);
  return (
    <ol className="steps" aria-label={`Status: ${STATUS[status]}`}>
      {STEPS.map((step, index) => (
        <li
          key={step}
          className={index < current ? "steps__done" : index === current ? `steps__now steps__now--${status}` : ""}
        >
          <span className="visually-hidden">{STATUS[step]}</span>
        </li>
      ))}
    </ol>
  );
}

/** Assigned against requested episodes as a ring, with the numbers in the middle. */
export function Ring({ request }: { request: DatasetRequest }) {
  const share = Math.min(request.assigned_count / request.episodes_requested, 1);
  return (
    <svg className="ring" viewBox="0 0 36 36" role="img" aria-label={`${request.assigned_count} of ${request.episodes_requested} episodes assigned`}>
      <circle cx="18" cy="18" r="15.5" className="ring__track" />
      {share > 0 && (
        <circle cx="18" cy="18" r="15.5" className="ring__fill" pathLength="100" strokeDasharray={`${share * 100} 100`} />
      )}
      <text x="18" y="21" textAnchor="middle">
        {request.assigned_count}/{request.episodes_requested}
      </text>
    </svg>
  );
}
