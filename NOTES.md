# Notes

How to run it is in the [README](README.md). **Stretch item:** background work.
Each assigned episode goes through a simulated export job, run by a separate
worker with safe retries, and the assignment page shows each export's status.

## 1. Design

```
organisations 1──* users 1──* requests 1──* status_history *──1 users (who changed it)
                                   │
                                   1──* assignments 1──1 episodes
                                            │
                                            1──1 export_jobs
```

Clients, and only clients, belong to an organisation (a CHECK). Requests belong
to the client who created them; every status change adds a `status_history` row
with the user, their role at the time, and when. A unique constraint on
`assignments.episode_id` keeps an episode in at most one request.

All state is in PostgreSQL, including the export queue. The session is a signed
cookie holding only the user id, and the user is reloaded on every request, so a
deactivation applies at once. If `SESSION_SECRET` is not set, each API process
picks a random one, so a restart logs everyone out.

**Hardest decisions**

1. **Concurrent changes to one request.** Delivering while someone unassigns an
   episode could leave a delivered request short. Every status change,
   assignment and unassignment takes a row lock on the request
   (`get_request(..., lock=True)`). A version column with retries would also
   work, but every assign and unassign would have to bump it and every caller
   would need retry logic. With about two operators per request, waiting on the
   lock costs almost nothing, and the "enough episodes" rule is checked while
   nobody else can change the request.
2. **Duplicates in the import.** A repeated episode id with the same values is a
   duplicate; with different values it is a conflict. Both are skipped and
   reported. Line 168 repeats `EP-00011` from line 3 as `good` instead of `bad`;
   the file cannot say which is right, so the first valid copy is kept, stored
   episodes are never overwritten, and the report shows both values.
3. **Delivery and exports.** The brief does not link them. I read an export as
   extracting the episode's content into the client's dataset (here it is
   simulated), so delivery is refused until every export has succeeded. A failed export can be retried by hand.

**Import rules.** Sample file: 189 rows, 171 imported, 2 duplicates, 2
conflicts, 14 rejected. Fields are trimmed; ids, robots, tasks and quality are
case-normalised. Rows are
rejected for blank fields, an unknown robot (`arm-99`), invalid quality
(`excellent`), wrong column count, a bad duration (`45.5`, `-5`, `999999`), or an
unreadable or future date. Dates are ISO 8601 or `dd/mm/yyyy HH:MM` (day first);
no time zone means UTC. The file is one transaction.

**Other decisions.** Another client's request returns 404, not 403. Clients see
staff changes by role, not name. Episodes are assigned only while a request is
in progress, and more than requested is allowed. A rejected request keeps its
assignments for rework. Deadlines and analytics days use Kigali time; the median
runs from submission to first delivery. An admin cannot deactivate themselves
or change their own role.

## 2. Left out, and the next two days

Left out: an analytics page, password reset, reactivating users, creating
organisations, request-list pagination, login throttling, and a way to correct a
stored episode. Next, in order: login throttling and revocable sessions;
pagination; Playwright tests of the three journeys (client creates a request,
operator assigns and delivers, client accepts or rejects); deployment, with the
frontend on Vercel or Netlify rewriting `/api` to a backend host not chosen yet;
an analytics page for operators and admins.

## 3. Something that went wrong

The first export queue test passed even with `SKIP LOCKED` removed. Mutation
testing showed it: the test checked that two workers never claim the same job,
but a plain `FOR UPDATE` also guarantees that, because the second worker waits
for the lock and then skips the job. The difference is only that workers wait
for each other. The test now holds worker A's lock, gives worker B a two-second
`lock_timeout`, and requires B to claim a different job; without `SKIP LOCKED`,
B times out and the test fails.

## 4. Security

Passwords are hashed with argon2id, and an unknown email is checked against a
dummy hash so timing does not reveal accounts. The session cookie is signed,
HttpOnly and `SameSite=Lax`, lasts 8 hours, and nothing is in `localStorage`.
State-changing requests from an `Origin` outside `ALLOWED_ORIGINS` are refused.
Apart from login, `/health` and the API docs, every endpoint needs a session
and its access rules are checked on the server; a test checks that each of
those routes refuses a request without a session. Pydantic limits
input (notes up to 2000 characters, passwords up to 128), CHECK constraints back
it up, and validation errors never echo the input. nginx caps uploads at 20 MB.

What worries me most:

1. **A client seeing another client's data.** Every lookup goes through
   `visible_requests`, and tests cover reading and changing another client's
   request, but a new endpoint that skips it would leak.
2. **Stolen or guessed credentials.** There is no login throttling, and a stolen
   cookie stays valid up to 8 hours, since logout only clears the browser's copy.

## 5. Scale

**10× users** (about 300, from roughly 30): the unpaginated request list breaks
first, then the single API process with 15 database connections, where slow
argon2 logins queue. Fix: pagination, several API processes with a shared
`SESSION_SECRET`, PgBouncer.

**100× episodes:** analytics read only the chosen range through covering
indexes, but very wide ranges would scan most of the table; a daily rollup
table or monthly partitions would fix that. The import holds every valid row in
memory in one transaction; I would `COPY` into a staging table and check in SQL
as a background job. I would move the episode list from offset to keyset
pagination, and archive finished export jobs after 12 months.

## 6. AI tooling

I used Claude Code throughout. Before each step I had it set out the options
and trade-offs, then decided; often I took its recommendation, and some choices
were my own answers to its questions, such as requests belonging to a person
and keeping Swagger public. It drafted the code, tests and documentation,
these notes included. The work was checked by running it: tests against real
PostgreSQL, mutation testing (breaking a rule on purpose to see a test fail),
starting from a clean copy, and CI on every push. That is how the weak queue test in section 3
came out. I also turned down output I did not want, such as a generic first
UI, which I replaced with my own palette.
