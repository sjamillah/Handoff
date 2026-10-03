import type { RequestStatus } from "./api";

/** Display names of statuses. Presentation only; the server owns the workflow. */
export const STATUS: Record<RequestStatus, string> = {
  submitted: "Submitted",
  in_progress: "In progress",
  delivered: "Delivered",
  accepted: "Accepted",
  rejected: "Rejected",
};

/** Button text for moving a request into each status. */
export const ACTION: Record<RequestStatus, string> = {
  submitted: "Submit",
  in_progress: "Start work",
  delivered: "Deliver",
  accepted: "Accept",
  rejected: "Reject",
};

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** A date such as "3 Oct 2026". Date-only values are read as local dates. */
export function formatDay(value: string): string {
  return day.format(new Date(value.length === 10 ? `${value}T00:00` : value));
}
