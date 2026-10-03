# Notes

The README has the run instructions. For the stretch item I did background work. Every assigned episode goes through a simulated export job. A separate worker runs the jobs and retries failures safely, and the assignment page shows the status of each export.

## 1. Design

```
organisations 1──* users 1──* requests 1──* status_history *──1 users (who changed it)
                                   │
                                   1──* assignments 1──1 episodes
                                            │
                                            1──1 export_jobs
```

Only clients belong to an organisation, and a CHECK enforces that. A request belongs to the client who created it. Every status change adds a row to `status_history` with who did it, their role at the time, and when. A unique constraint on `assignments.episode_id` means an episode can be in only one request.

Everything lives in PostgreSQL, the export queue too. The session is a signed cookie that holds just the user id. I reload the user on every request, so deactivating someone takes effect straight away. If `SESSION_SECRET` isn't set, each API process makes up its own, so a restart logs everyone out.

**Hardest decisions**

1. **Two people changing one request at once.** If someone delivers while someone else unassigns an episode, the delivered request could end up short. So every status change, assign and unassign locks the request row first (`get_request(..., lock=True)`). I could have used a version column with retries, but then every assign and unassign has to bump it and every caller needs retry logic. There are about two operators per request, so waiting on a lock costs almost nothing. It also means the "enough episodes" check runs while nobody else can touch the request.
2. **Duplicates in the import.** The same episode id with the same values is a duplicate. The same id with different values is a conflict. I skip both and report them. Line 168 repeats `EP-00011` from line 3, but says `good` instead of `bad`. The file can't tell me which one is right, so I keep the first valid copy and never overwrite what's stored. The report shows both values.
3. **Delivery and exports.** The brief doesn't connect them. I treated an export as pulling the episode's content into the client's dataset (it's simulated here), so a request can't be delivered until every export has succeeded. A failed export can be retried by hand.

**Import rules.** On the sample file: 189 rows, 171 imported, 2 duplicates, 2 conflicts, 14 rejected. I trim every field and normalise case on ids, robots, tasks and quality. A row is rejected if a field is blank, the robot is unknown (`arm-99`), the quality is invalid (`excellent`), the column count is wrong, the duration is bad (`45.5`, `-5`, `999999`), or the date can't be read or is in the future. Dates are ISO 8601 or `dd/mm/yyyy HH:MM`, day first. No time zone means UTC. The whole file runs in one transaction.

**Other decisions.** Another client's request gives a 404, not a 403. Clients see staff changes by role, not by name. Episodes can only be assigned while a request is in progress, and assigning more than requested is allowed. A rejected request keeps its assignments for the rework. Deadlines and analytics days use Kigali time. The median runs from submission to first delivery. An admin can't deactivate themselves or change their own role.

## 2. Left out, and the next two days

Left out: an analytics page, password reset, reactivating users, creating organisations, pagination on the request list, login throttling, and a way to correct a stored episode.

With two more days I'd go in this order: login throttling and revocable sessions, pagination, Playwright tests for three journeys (client creates a request, operator assigns and delivers, client accepts or rejects), deployment, then an analytics page for operators and admins. For deployment the frontend would go on Vercel or Netlify, rewriting `/api` to a backend host I haven't picked yet.

## 3. Something that went wrong

My first export queue test passed even with `SKIP LOCKED` removed. Mutation testing caught it. The test checked that two workers never claim the same job, but a plain `FOR UPDATE` guarantees that too. All `SKIP LOCKED` changes is that a worker doesn't wait on a job someone else has locked.

So I rewrote the test. Worker A holds its lock, worker B gets a two second `lock_timeout`, and B has to claim a different job. Without `SKIP LOCKED`, B times out and the test fails.

## 4. Security

Passwords are hashed with argon2id. If the email doesn't exist, I still check against a dummy hash, so the response time doesn't show which accounts exist. The session cookie is signed, HttpOnly and `SameSite=Lax`, and lasts 8 hours. Nothing goes in `localStorage`. A state-changing request from an `Origin` that isn't in `ALLOWED_ORIGINS` is refused.

Apart from login, `/health` and the API docs, every endpoint needs a session, and the access rules are checked on the server. A test makes sure each of those routes refuses a request with no session. Pydantic limits the input (notes up to 2000 characters, passwords up to 128) and CHECK constraints back that up. Validation errors don't echo the input back. nginx caps uploads at 20 MB.

What worries me most:

1. **A client seeing another client's data.** Every lookup goes through `visible_requests`, and tests cover reading and changing another client's request. But a new endpoint that skips it would leak.
2. **Stolen or guessed credentials.** There's no login throttling, and a stolen cookie stays valid for up to 8 hours, because logout only clears the browser's copy.

## 5. Scale

**10× users.** I'm assuming about 30 users today, so 300. The request list isn't paginated, and that breaks first. Next is the single API process with 15 database connections, where slow argon2 logins start to queue. I'd add pagination, run several API processes with the same `SESSION_SECRET`, and put PgBouncer in front.

**100× episodes.** The episode analytics only read the date range you ask for, using indexes, but a very wide range would scan most of the table. A daily rollup table or monthly partitions would fix that. The import keeps every valid row in memory in one transaction. I'd `COPY` into a staging table and check the rows in SQL as a background job. The episode list should move from offset to keyset pagination. Finished export jobs I'd archive after 12 months.

## 6. AI tooling

I used Claude Code for the whole build. At each step I had it lay out the options and trade-offs first, and then I decided. Some choices were my own answers to its questions, like requests belonging to a person and keeping Swagger public. It drafted the code, the tests and the documentation, including these notes.

The work was checked by running it: tests against real PostgreSQL, mutation testing (breaking a rule on purpose to see if a test fails), starting from a clean copy, and CI on every push. That's how the weak queue test in section 3 was found. I also rejected output I didn't want, like a generic first UI, which I replaced with my own palette.
