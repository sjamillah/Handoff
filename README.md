# Handoff

[![CI](https://github.com/sjamillah/Handoff/actions/workflows/ci.yml/badge.svg)](https://github.com/sjamillah/Handoff/actions/workflows/ci.yml)

Handoff is the Dataset Request Desk: an internal platform for a robotics data
collection company. Clients request datasets of recorded robot episodes,
operators import episodes from the recording system's CSV export, assign them to
requests and deliver, and clients accept or reject each delivery. Every status
change is recorded with who made it and when.

It is a FastAPI backend on PostgreSQL with Alembic migrations, and a React +
TypeScript frontend served by nginx. Design decisions, trade-offs and what was
left out are in [NOTES.md](NOTES.md).

## Start everything

Requires Docker with Compose v2. No `.env` file is needed.

```sh
docker compose up --build --wait
```

This starts PostgreSQL, runs the migrations, seeds the users, imports
`backend/seed/episodes.csv`, and starts the API, the export worker and the web app. `--wait` returns
once the API is healthy and the web app is up.

| What | Where |
|---|---|
| Web app | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| API docs (ReDoc) | http://localhost:8000/redoc |
| Health check | http://localhost:8000/health |

To stop, and to start again from an empty database:

```sh
docker compose down -v
```

## Seed users (development only)

These accounts are created on every start if they do not exist yet. The passwords
come from the brief and are stored as argon2 hashes. They are for local
development only; set your own with the `SEED_*_PASSWORD` variables for anything
else.

| Role | Email | Password |
|---|---|---|
| Admin | admin@example.com | admin123 |
| Operator | ops1@example.com | ops123 |
| Operator | ops2@example.com | ops123 |
| Client (Acme Robotics) | client-a@example.com | client123 |
| Client (Beta Labs) | client-b@example.com | client123 |

## Run the tests

```sh
docker compose run --rm --build tests
```

The tests run against a separate PostgreSQL database, `handoff_test`, which is
dropped, recreated and migrated on every run; your development data is not
touched. `--build` matters: the test image contains a copy of the code, so
without it you test whatever was there at the last build.

They cover authorization, every status transition, the assignment rules and
import idempotency. GitHub Actions (`.github/workflows/ci.yml`) runs the same lint
and tests, and type-checks and builds the frontend, on every push and pull request.
To lint locally as well:

```sh
docker compose run --rm --build tests sh -c "ruff format --check . && ruff check ."
```

## Import episodes

The import is safe to run more than once: existing episodes are never changed,
so a second run of the same file creates no rows. Each run reports how many
rows were imported, skipped as duplicates, skipped as conflicts or rejected, and
why, line by line. Dates in `dd/mm/yyyy HH:MM` form are read day first, and
times without a time zone are taken as UTC.

From the command line, inside the running API container:

```sh
docker compose exec api python -m app.import_episodes seed/episodes.csv
```

For another file, copy it in first:

```sh
docker compose cp my-export.csv api:/tmp/my-export.csv
docker compose exec api python -m app.import_episodes /tmp/my-export.csv
```

Through the API, as an operator or admin (`POST /episodes/import`, a file upload):

```sh
curl -c cookies.txt -H "Content-Type: application/json" \
  -d '{"email":"ops1@example.com","password":"ops123"}' http://localhost:8000/auth/login
curl -b cookies.txt -F "file=@backend/seed/episodes.csv" http://localhost:8000/episodes/import
```

The same endpoint is available in Swagger at http://localhost:8000/docs.

## Export jobs

Every assigned episode gets a simulated export job in the same transaction as the
assignment. A separate `worker` service claims jobs with `SELECT ... FOR UPDATE SKIP
LOCKED`, runs each one (2 to 5 seconds, failing 20% of the time) outside any
transaction under a 30-second lease, and retries failures with a doubling delay up
to 5 attempts. A job left running by a crashed worker is taken over when its lease
expires. Operators see each episode's export status on the assignment page, which
refreshes every 2 seconds until every export has finished, and can retry a failed
one. A request can only be delivered once all its exports have succeeded.

Run more workers with `docker compose up -d --scale worker=3`, and follow them with
`docker compose logs -f worker`.

## Analytics at 5 million episodes

`GET /analytics?from=YYYY-MM-DD&to=YYYY-MM-DD` (operators and admins) returns
episodes per day per robot, request counts by status with the median time from
submission to first delivery, and the top five tasks by good episodes. Each figure
is one aggregate query in PostgreSQL.

The two episode queries are range scans on `recorded_at`, so they cost roughly
what the chosen range contains, not the whole table. Covering indexes,
`(recorded_at, robot_id)` and a partial `(recorded_at, task_name) WHERE quality =
'good'`, let PostgreSQL answer both from the index without reading the table. On
200,000 generated episodes a three-month range takes about 27 ms and 12 ms. At 5
million episodes a month-long range is around 400,000 index entries, still well
under a second while the visibility map is current. A multi-year range reads most
of the table and becomes a sequential scan of about a gigabyte; at that point the
fix is monthly partitions on `recorded_at`, or a daily rollup table of counts per
day, robot, task and quality that the import maintains, which keeps every range
small whatever the episode count.

The request figures depend on the number of requests, not episodes, so 5 million
episodes does not change them.

## Configuration

Everything has a working default. To change something, copy `.env.example` to
`.env` and fill in only what you need; empty values keep the default.

| Variable | Default | Purpose |
|---|---|---|
| `WEB_PORT`, `API_PORT` | 3000, 8000 | Host ports for the web app and the API |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | handoff | Database credentials, used when the volume is first created |
| `SEED_ADMIN_PASSWORD`, `SEED_OPERATOR_PASSWORD`, `SEED_CLIENT_PASSWORD` | as in the table above | Passwords given to the seed users when they are first created |
| `SESSION_SECRET` | random at startup | Signs the session cookie. Set it so sessions survive restarts |
| `SESSION_HTTPS_ONLY` | false | Set to true behind HTTPS |
| `APP_TIMEZONE` | Africa/Kigali | The business time zone, used for deadlines and analytics days |
| `EXPORT_FAILURE_RATE`, `EXPORT_MIN_SECONDS`, `EXPORT_MAX_SECONDS` | 0.2, 2, 5 | Simulated export failure rate and duration |
| `EXPORT_MAX_ATTEMPTS`, `EXPORT_LEASE_SECONDS` | 5, 30 | Attempts per export, and how long a worker owns a running job |
| `ALLOWED_ORIGINS` | localhost and 127.0.0.1 on both ports | Origins allowed to send state-changing requests (CSRF protection) |

## Project layout

```
.
├── docker-compose.yml        db, api, worker, web; tests and bench profiles
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py           app setup: middleware, routers, error handlers
│   │   ├── config.py         settings from environment variables
│   │   ├── models/           SQLAlchemy models, one file per table
│   │   ├── schemas/          request and response bodies, by topic
│   │   ├── routers/          HTTP endpoints only
│   │   ├── services/         business rules: workflow, assignments, import, analytics
│   │   ├── csrf.py           Origin check for state-changing requests
│   │   ├── request_logging.py one JSON log line per request
│   │   ├── seed.py           seed users (python -m app.seed)
│   │   ├── worker.py         export worker (python -m app.worker)
│   │   └── import_episodes.py CSV import CLI (python -m app.import_episodes)
│   ├── migrations/           Alembic migrations
│   ├── tests/                pytest suite
│   └── seed/episodes.csv     the sample export from the brief
└── frontend/
    ├── src/
    │   ├── api.ts            API types and calls
    │   ├── pages/            login, client requests, new request, operator requests, assign
    │   ├── ui.tsx            shared components
    │   └── styles.css
    └── nginx.conf            serves the app and forwards /api to the backend
```

## Troubleshooting

- **A port is already in use.** Set `WEB_PORT` or `API_PORT`, for example
  `WEB_PORT=3100 docker compose up --build --wait`. The allowed origins follow
  the ports automatically.
- **Login fails after changing database or seed settings.** PostgreSQL and the
  seed only read them when the volume is first created. Run
  `docker compose down -v` to start from an empty database.
- **The first start is slow.** It downloads images and installs Python and npm
  packages, which needs network access to Docker Hub, PyPI and npm.
