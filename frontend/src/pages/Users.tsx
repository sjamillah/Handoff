import { useEffect, useState, type FormEvent } from "react";

import { api, ApiError, errorMessage, type Role, type User } from "../api";
import { useAuth } from "../auth";
import { Alert, Band, Button, Field } from "../ui";

const ROLES: Role[] = ["client", "operator", "admin"];
const STAFF_ROLES: Role[] = ["operator", "admin"];

/** Admin screen: every user, a form to add one, and role changes and deactivation. */
export function Users() {
  const me = useAuth().user;
  const [users, setUsers] = useState<User[] | null>(null);
  const [organisations, setOrganisations] = useState<string[]>([]);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [newRole, setNewRole] = useState<Role>("client");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => api.users().then(setUsers, (caught) => setMessage({ error: true, text: errorMessage(caught) }));
  useEffect(() => {
    load();
    api.organisations().then(setOrganisations, () => setOrganisations([]));
  }, []);

  async function act(key: string, action: () => Promise<unknown>, done: string) {
    setBusy(key);
    setMessage(null);
    try {
      await action();
      setMessage({ error: false, text: done });
      await load();
    } catch (caught) {
      setMessage({ error: true, text: errorMessage(caught) });
    } finally {
      setBusy(null);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    setErrors({});
    await act("create", async () => {
      try {
        await api.createUser({ ...data, organisation: data.organisation || null });
        form.reset();
        setNewRole("client");
      } catch (caught) {
        if (caught instanceof ApiError) setErrors(caught.fieldErrors);
        throw caught;
      }
    }, `Added ${data.email}.`);
  }

  function changeRole(user: User, role: Role) {
    act(`role-${user.id}`, () => api.changeRole(user.id, role, null), `${user.email} is now ${role}.`);
  }

  return (
    <>
      <Band title="Users" />
      <main className="page">
        {message && <Alert error={message.error}>{message.text}</Alert>}
        <form className="panel form form--inline" onSubmit={create} noValidate>
          <Field id="name" label="Name" error={errors.name}>
            <input id="name" name="name" aria-invalid={Boolean(errors.name)} />
          </Field>
          <Field id="email" label="Email" error={errors.email}>
            <input id="email" name="email" type="email" aria-invalid={Boolean(errors.email)} />
          </Field>
          <Field id="password" label="Password" error={errors.password}>
            <input id="password" name="password" type="password" aria-invalid={Boolean(errors.password)} />
          </Field>
          <Field id="role" label="Role">
            <select id="role" name="role" value={newRole} onChange={(event) => setNewRole(event.target.value as Role)}>
              {ROLES.map((role) => (
                <option key={role}>{role}</option>
              ))}
            </select>
          </Field>
          {newRole === "client" && (
            <Field id="organisation" label="Organisation" error={errors.organisation}>
              <select id="organisation" name="organisation">
                {organisations.map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            </Field>
          )}
          <Button type="submit" loading={busy === "create"}>
            Add user
          </Button>
        </form>
        {!users ? (
          <p className="muted">Loading…</p>
        ) : (
          <div className="panel table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Organisation</th>
                  <th>Role</th>
                  <th>
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className={user.is_active ? "" : "inactive"}>
                    <td>
                      {user.name}
                      {user.id === me?.id && <span className="muted"> (you)</span>}
                    </td>
                    <td>{user.email}</td>
                    <td>{user.organisation_name ?? "-"}</td>
                    <td>
                      {user.is_active && user.id !== me?.id ? (
                        <select
                          aria-label={`Role of ${user.email}`}
                          value={user.role}
                          disabled={busy !== null}
                          onChange={(event) => changeRole(user, event.target.value as Role)}
                        >
                          {(user.role === "client" ? ROLES : STAFF_ROLES).map((role) => (
                            <option key={role}>{role}</option>
                          ))}
                        </select>
                      ) : (
                        user.role
                      )}
                    </td>
                    <td>
                      <div className="actions">
                        {!user.is_active ? (
                          <span className="muted">Deactivated</span>
                        ) : (
                          user.id !== me?.id && (
                            <Button
                              variant="danger"
                              loading={busy === `off-${user.id}`}
                              disabled={busy !== null}
                              onClick={() => act(`off-${user.id}`, () => api.deactivateUser(user.id), `${user.email} was deactivated.`)}
                            >
                              Deactivate
                            </Button>
                          )
                        )}
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
