import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage, type DatasetRequest, type EpisodePage, type ExportList } from "../api";
import { formatDay } from "../format";
import { Alert, Band, Button, Ring, StatusBadge } from "../ui";

const POLL_MS = 2000;

/**
 * Export status of the request's episodes, refreshed every two seconds until the
 * server reports that every export has finished. Changing ``version`` starts it again.
 */
function useExports(id: number, version: number): ExportList | null {
  const [list, setList] = useState<ExportList | null>(null);
  useEffect(() => {
    let stopped = false;
    let timer = 0;
    const load = () =>
      api.exports(id).then(
        (data) => {
          if (stopped) return;
          setList(data);
          if (!data.finished) timer = window.setTimeout(load, POLL_MS);
        },
        () => {
          if (!stopped) timer = window.setTimeout(load, POLL_MS);
        },
      );
    load();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [id, version]);
  return list;
}

/** Pick episodes for one request by task and quality, then assign them. The server checks every rule. */
export function Assign() {
  const id = Number(useParams().requestId);
  const [request, setRequest] = useState<DatasetRequest | null>(null);
  const [filters, setFilters] = useState<{ task: string; quality: string } | null>(null);
  const [page, setPage] = useState<EpisodePage | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<{ error: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const exports = useExports(id, version);
  const fail = (caught: unknown) => setResult({ error: true, text: errorMessage(caught) });

  useEffect(() => {
    api.request(id).then((loaded) => {
      setRequest(loaded);
      setFilters({ task: loaded.task_name, quality: "" });
    }, fail);
  }, [id]);

  useEffect(() => {
    if (filters) api.episodes(filters.task, filters.quality).then(setPage, fail);
  }, [filters]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSelected([]);
    setFilters({ task: String(form.get("task")), quality: String(form.get("quality")) });
  }

  const toggle = (episodeId: string) =>
    setSelected((list) => (list.includes(episodeId) ? list.filter((x) => x !== episodeId) : [...list, episodeId]));
  const allIds = page?.items.map((episode) => episode.episode_id) ?? [];
  const allSelected = allIds.length > 0 && allIds.every((x) => selected.includes(x));

  async function assign() {
    setBusy(true);
    try {
      const done = await api.assign(id, selected);
      setResult({ error: false, text: `Assigned ${done.assigned.length} episodes.` });
      setSelected([]);
      setRequest(await api.request(id));
      setFilters((current) => current && { ...current });
      setVersion((n) => n + 1);
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(false);
    }
  }

  async function retry(episodeId: string) {
    try {
      await api.retryExport(id, episodeId);
      setVersion((n) => n + 1);
    } catch (caught) {
      fail(caught);
    }
  }

  return (
    <>
      <Band title={`Assign episodes${request ? ` to #${request.id}` : ""}`}>
        <Link to="/" className="back">
          ← Requests
        </Link>
      </Band>
      <main className="page">
        {request && (
          <section className="panel summary">
            <Ring request={request} />
            <div>
              <p className="summary__task">{request.task_name}</p>
              <p className="muted">
                {request.client_name} · due {formatDay(request.deadline)}
              </p>
            </div>
            <StatusBadge status={request.status} />
          </section>
        )}
        {request && !request.can_assign && <Alert>This request does not take assignments in its current status.</Alert>}
        {exports && exports.jobs.length > 0 && (
          <section className="panel exports" aria-label="Exports">
            <h2>
              Exports
              <span className="muted">{exports.finished ? " · finished" : " · updating every 2 seconds"}</span>
            </h2>
            <table>
              <thead>
                <tr>
                  <th>Episode</th>
                  <th>Export</th>
                  <th>Attempts</th>
                  <th>
                    <span className="visually-hidden">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {exports.jobs.map((job) => (
                  <tr key={job.episode_id}>
                    <td className="mono">{job.episode_id}</td>
                    <td>
                      <span className={`export export--${job.status}`}>{job.status}</span>
                    </td>
                    <td>
                      {job.attempts}/{job.max_attempts}
                    </td>
                    <td>
                      <div className="actions">
                        {job.status === "failed" && (
                          <>
                            <span className="field__error">{job.last_error}</span>
                            <Button variant="plain" onClick={() => retry(job.episode_id)}>
                              Retry
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        {filters && (
          <form className="filters" onSubmit={applyFilters}>
            <label>
              Task name
              <input name="task" defaultValue={filters.task} />
            </label>
            <label>
              Quality
              <select name="quality" defaultValue={filters.quality}>
                <option value="">Good or usable</option>
                <option value="good">Good</option>
                <option value="usable">Usable</option>
              </select>
            </label>
            <Button type="submit" variant="plain">
              Filter
            </Button>
          </form>
        )}
        {result && <Alert error={result.error}>{result.text}</Alert>}
        <div className="panel">
          <label className="row row--head">
            <input type="checkbox" checked={allSelected} onChange={() => setSelected(allSelected ? [] : allIds)} />
            {page ? `${page.total} available${page.total > page.items.length ? `, first ${page.items.length} shown` : ""}` : "Loading…"}
          </label>
          {page?.items.map((episode) => (
            <label key={episode.episode_id} className="row">
              <input
                type="checkbox"
                checked={selected.includes(episode.episode_id)}
                onChange={() => toggle(episode.episode_id)}
              />
              <span className="mono">{episode.episode_id}</span>
              <span className="muted">
                {episode.robot_id} · {formatDay(episode.recorded_at)} · {episode.duration_seconds}s
              </span>
              <span className={`quality quality--${episode.quality}`}>{episode.quality}</span>
            </label>
          ))}
        </div>
        <div className="panel bar">
          <span>{selected.length} selected</span>
          <Button onClick={assign} loading={busy} disabled={selected.length === 0 || !request?.can_assign}>
            Assign selected episodes
          </Button>
        </div>
      </main>
    </>
  );
}
