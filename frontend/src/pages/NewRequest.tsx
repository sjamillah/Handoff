import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError, errorMessage } from "../api";
import { Alert, Band, Button, Field } from "../ui";

/** Form for a new request. The server validates every field and its messages are shown. */
export function NewRequest() {
  const navigate = useNavigate();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const created = await api.createRequest({
        task_name: form.get("task_name"),
        episodes_requested: Number(form.get("episodes_requested")),
        deadline: form.get("deadline"),
        notes: form.get("notes") || null,
      });
      navigate("/", { state: { created: created.id } });
    } catch (caught) {
      setErrors(caught instanceof ApiError ? caught.fieldErrors : {});
      setMessage(errorMessage(caught));
      setBusy(false);
    }
  }

  const invalid = (name: string) => ({
    "aria-invalid": Boolean(errors[name]),
    "aria-describedby": errors[name] ? `${name}-error` : undefined,
  });

  return (
    <>
      <Band title="New request" />
      <main className="page page--narrow">
        <form className="panel form" onSubmit={submit} noValidate>
          {message && <Alert error>{message}</Alert>}
          <Field id="task_name" label="Task" error={errors.task_name}>
            <input id="task_name" name="task_name" placeholder="pick cup" {...invalid("task_name")} />
          </Field>
          <div className="form__row">
            <Field id="episodes_requested" label="Episodes" error={errors.episodes_requested}>
              <input id="episodes_requested" name="episodes_requested" type="number" {...invalid("episodes_requested")} />
            </Field>
            <Field id="deadline" label="Deadline" error={errors.deadline}>
              <input id="deadline" name="deadline" type="date" {...invalid("deadline")} />
            </Field>
          </div>
          <Field id="notes" label="Notes (optional)" error={errors.notes}>
            <textarea id="notes" name="notes" rows={3} {...invalid("notes")} />
          </Field>
          <div className="actions">
            <Link to="/" className="button button--plain">
              Cancel
            </Link>
            <Button type="submit" loading={busy}>
              Submit request
            </Button>
          </div>
        </form>
      </main>
    </>
  );
}
