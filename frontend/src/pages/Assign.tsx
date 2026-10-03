import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage, type DatasetRequest, type EpisodePage } from "../api";
import { formatDay } from "../format";
import { Alert, Band, Button, Ring, StatusBadge } from "../ui";

/** Pick episodes for one request by task and quality, then assign them. The server checks every rule. */
export function Assign() {
  const id = Number(useParams().requestId);
  const [request, setRequest] = useState<DatasetRequest | null>(null);
  const [filters, setFilters] = useState<{ task: string; quality: string } | null>(null);
  const [page, setPage] = useState<EpisodePage | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<{ error: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
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
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(false);
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
