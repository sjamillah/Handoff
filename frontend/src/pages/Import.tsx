import { useState, type FormEvent } from "react";

import { api, errorMessage, type ImportReport, type ImportRow } from "../api";
import { Alert, Band, Button } from "../ui";

const COUNTS: [keyof ImportReport, string][] = [
  ["imported", "Imported"],
  ["duplicates", "Duplicates"],
  ["conflicts", "Conflicts"],
  ["rejected", "Rejected"],
];

const PRIORITY: Record<ImportRow["outcome"], number> = { rejected: 0, conflict: 1, duplicate: 2 };

/** Rows needing attention first: rejected, then conflicts, then duplicates, each by line. */
function byAttention(rows: ImportRow[]): ImportRow[] {
  return [...rows].sort((a, b) => PRIORITY[a.outcome] - PRIORITY[b.outcome] || a.line - b.line);
}

/** Upload an episodes CSV and show the server's report, problems first. */
export function Import() {
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = new FormData(event.currentTarget).get("file");
    if (!(file instanceof File) || !file.name) return;
    setBusy(true);
    setError(null);
    try {
      setReport(await api.importCsv(file));
    } catch (caught) {
      setReport(null);
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Band title="Import episodes" />
      <main className="page">
        <form className="panel upload" onSubmit={upload}>
          <label htmlFor="file">CSV export from the recording system</label>
          <input id="file" name="file" type="file" accept=".csv,text/csv" required />
          <Button type="submit" loading={busy}>
            Import
          </Button>
          <p className="muted small">Safe to repeat: episodes already imported are reported, never changed.</p>
        </form>
        {error && <Alert error>{error}</Alert>}
        {report && (
          <>
            <div className="counts">
              {COUNTS.map(([key, label]) => (
                <div key={key} className={`panel count count--${key}`}>
                  <strong>{report[key] as number}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            {report.rows.length > 0 && (
              <div className="panel table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Line</th>
                      <th>Episode</th>
                      <th>Outcome</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byAttention(report.rows).map((row) => (
                      <tr key={row.line}>
                        <td>{row.line}</td>
                        <td className="mono">{row.episode_id ?? "-"}</td>
                        <td>
                          <span className={`outcome outcome--${row.outcome}`}>{row.outcome}</span>
                        </td>
                        <td className="wrap">{row.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
