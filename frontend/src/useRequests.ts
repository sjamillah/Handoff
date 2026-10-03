import { useEffect, useState } from "react";

import { api, errorMessage, type DatasetRequest, type RequestStatus } from "./api";

/**
 * Requests visible to the current user, and a move function. The server decides
 * every move; a refused move leaves the list unchanged and keeps the server's message.
 */
export function useRequests(status?: RequestStatus) {
  const [requests, setRequests] = useState<DatasetRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    setRequests(null);
    api.requests(status).then(setRequests, (caught) => setError(errorMessage(caught)));
  }, [status]);

  async function move(id: number, to: RequestStatus) {
    setBusy(`${id}:${to}`);
    setError(null);
    try {
      const updated = await api.move(id, to);
      setRequests((list) => list && list.map((item) => (item.id === id ? updated : item)));
    } catch (caught) {
      setError(`Request #${id}: ${errorMessage(caught)}`);
    } finally {
      setBusy(null);
    }
  }

  return { requests, error, busy, move };
}
