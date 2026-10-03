/** API types and calls. Every path goes through /api, which is the same origin as the app. */

export type Role = "client" | "operator" | "admin";
export type RequestStatus = "submitted" | "in_progress" | "delivered" | "accepted" | "rejected";
export type Quality = "good" | "usable" | "bad";

export interface User {
  id: number;
  name: string;
  role: Role;
  organisation_name: string | null;
}

export interface DatasetRequest {
  id: number;
  client_name: string;
  task_name: string;
  episodes_requested: number;
  deadline: string;
  notes: string | null;
  status: RequestStatus;
  assigned_count: number;
  available_transitions: RequestStatus[];
  can_assign: boolean;
}

export interface Episode {
  episode_id: string;
  robot_id: string;
  task_name: string;
  recorded_at: string;
  duration_seconds: number;
  quality: Quality;
}

export interface EpisodePage {
  items: Episode[];
  total: number;
}

export const UNAUTHORIZED = "handoff:unauthorized";

/** Error from the API, with its message and any per-field validation messages. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

/** Send a JSON request. A 401 on anything but login tells the app the session has ended. */
async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 401 && path !== "/auth/login") {
    window.dispatchEvent(new Event(UNAUTHORIZED));
  }
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.ok) {
    return data as T;
  }
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    const fields = Object.fromEntries(
      detail.map((issue: { loc: string[]; msg: string }) => [
        issue.loc[issue.loc.length - 1],
        issue.msg.replace(/^Value error, /, ""),
      ]),
    );
    throw new ApiError("Some fields need attention.", fields);
  }
  throw new ApiError(typeof detail === "string" ? detail : "Something went wrong.");
}

/** The server's message for an error, or a generic one when the server could not be reached. */
export function errorMessage(caught: unknown): string {
  return caught instanceof ApiError ? caught.message : "Could not reach the server.";
}

export const api = {
  login: (email: string, password: string) => request<User>("/auth/login", "POST", { email, password }),
  logout: () => request<null>("/auth/logout", "POST"),
  me: () => request<User>("/auth/me"),
  requests: (status?: RequestStatus) => request<DatasetRequest[]>(`/requests${status ? `?status=${status}` : ""}`),
  request: (id: number) => request<DatasetRequest>(`/requests/${id}`),
  createRequest: (body: object) => request<DatasetRequest>("/requests", "POST", body),
  move: (id: number, toStatus: RequestStatus) =>
    request<DatasetRequest>(`/requests/${id}/transitions`, "POST", { to_status: toStatus }),
  episodes: (taskName: string, quality: string) =>
    request<EpisodePage>(
      `/episodes?${new URLSearchParams({ assignable: "true", limit: "100", task_name: taskName, ...(quality && { quality }) })}`,
    ),
  assign: (id: number, episodeIds: string[]) =>
    request<{ assigned: string[]; assigned_count: number }>(`/requests/${id}/assignments`, "POST", {
      episode_ids: episodeIds,
    }),
};
