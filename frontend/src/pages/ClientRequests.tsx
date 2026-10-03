import { Link, useLocation } from "react-router-dom";

import { formatDay } from "../format";
import { Alert, Band, Moves, Progress, StatusBadge, Steps } from "../ui";
import { useRequests } from "../useRequests";

/** The client's own requests, with accept and reject wherever the server offers them. */
export function ClientRequests() {
  const { requests, error, busy, move } = useRequests();
  const created = (useLocation().state as { created?: number } | null)?.created;

  return (
    <>
      <Band title="Your requests">
        <Link to="/requests/new" className="button button--primary">
          New request
        </Link>
      </Band>
      <main className="page">
        {created && <Alert>Request #{created} submitted.</Alert>}
        {error && <Alert error>{error}</Alert>}
        {!requests ? (
          <p className="muted">Loading…</p>
        ) : requests.length === 0 ? (
          <p className="panel empty">No requests yet. Start with “New request”.</p>
        ) : (
          <ul className="list">
            {requests.map((request) => (
              <li key={request.id} className="list__row">
                <div>
                  <p className="list__title">
                    <span className="muted">#{request.id}</span> {request.task_name}
                  </p>
                  <p className="muted">
                    Due {formatDay(request.deadline)}
                    {request.notes && ` · ${request.notes}`}
                  </p>
                  <Steps status={request.status} />
                </div>
                <Progress request={request} />
                <StatusBadge status={request.status} />
                <div className="actions">
                  <Moves request={request} busy={busy} onMove={(to) => move(request.id, to)} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
