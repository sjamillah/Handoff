import { useState } from "react";
import { Link } from "react-router-dom";

import type { RequestStatus } from "../api";
import { formatDay, STATUS } from "../format";
import { Alert, Band, Moves, Progress, StatusBadge } from "../ui";
import { useRequests } from "../useRequests";

const FILTERS = [undefined, ...(Object.keys(STATUS) as RequestStatus[])];

/** Every request, filtered by status, with the moves and assignment link the server allows. */
export function OperatorRequests() {
  const [status, setStatus] = useState<RequestStatus | undefined>();
  const { requests, error, busy, move } = useRequests(status);

  return (
    <>
      <Band title="Requests">
        <div className="tabs" role="group" aria-label="Filter by status">
          {FILTERS.map((option) => (
            <button key={option ?? "all"} type="button" aria-pressed={status === option} onClick={() => setStatus(option)}>
              {option ? STATUS[option] : "All"}
            </button>
          ))}
        </div>
      </Band>
      <main className="page">
        {error && <Alert error>{error}</Alert>}
        {!requests ? (
          <p className="muted">Loading…</p>
        ) : requests.length === 0 ? (
          <p className="panel empty">No requests with this status.</p>
        ) : (
          <div className="panel table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Client</th>
                  <th>Episodes</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th>
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {requests.map((request) => (
                  <tr key={request.id}>
                    <td>
                      <span className="muted">#{request.id}</span> {request.task_name}
                    </td>
                    <td>{request.client_name}</td>
                    <td>
                      <Progress request={request} />
                    </td>
                    <td>{formatDay(request.deadline)}</td>
                    <td>
                      <StatusBadge status={request.status} />
                    </td>
                    <td>
                      <div className="actions">
                        {request.can_assign && (
                          <Link to={`/requests/${request.id}/assign`} className="button button--plain">
                            Assign
                          </Link>
                        )}
                        <Moves request={request} busy={busy} onMove={(to) => move(request.id, to)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  );
}
