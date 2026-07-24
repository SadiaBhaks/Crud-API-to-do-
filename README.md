# Task API

A to-do list API — full CRUD, now running against a real **PostgreSQL**
database inside **Docker**. Built for the FlyRank Internship Backend Track
(Assignment 1 → 2 → 3, the third storage swap in the same repo).

Built with **Python 3 + FastAPI + psycopg** (the standard raw Postgres
driver), containerized with Docker Compose.

## The storage journey so far

| Assignment | Where tasks live | What runs it |
|---|---|---|
| A1 | a list in memory | your program |
| A2 | a `tasks.db` file | your disk (SQLite) |
| A3 (this one) | rows in Postgres | a container — a real database server |

The API on top never changed. That's the whole point of keeping every
database call inside one file, `db.py` — swapping storage only ever means
rewriting that file, never the routes.

## One command to run everything

```bash
cp .env.example .env
docker compose up
```

That's it — Docker builds the app image, starts Postgres, waits for
Postgres to be healthy, then starts the API. On first run the `tasks`
table is created and seeded with 3 example tasks automatically.

Then open:
- `http://localhost:8000/` — API description
- `http://localhost:8000/health` — health check (now also pings the database)
- `http://localhost:8000/docs` — **Swagger UI**

Stop everything with `docker compose down` (your data survives, kept in
the `taskdata` volume) — add `-v` (`docker compose down -v`) only if you
want to wipe the database too.

## Environment variables

Copy `.env.example` to `.env` — that's the only setup step. `.env` is
git-ignored, since a database password should never be committed;
`.env.example` documents which key is needed:

```
DATABASE_URL=postgresql://postgres:dev@localhost:5432/tasks
```

Inside Docker Compose, the `api` service actually connects to the `db`
service using the service name (`db`) instead of `localhost` — Compose
sets that automatically in `compose.yaml`, so the `.env` value above is
mainly for running the app directly on your machine against a
separately-started Postgres container.

## Running without Compose (optional, for local development)

```bash
docker run --name taskdb -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=tasks \
  -p 5432:5432 -v taskdata:/var/lib/postgresql/data -d postgres

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Endpoints

Identical to Assignments 1 and 2 — only `db.py` changed, from SQLite
queries to Postgres queries.

| CRUD | Method | Path | Description |
|------|--------|------|-------------|
| — | GET | `/` | API description |
| — | GET | `/health` | Health check, pings the database → `{"status": "ok", "db": "ok"}` |
| Read | GET | `/tasks` | List all tasks (supports `?done=`, `?search=`, `?limit=`, `?offset=`) |
| Read | GET | `/tasks/{id}` | Get one task, or `404` if it doesn't exist |
| Create | POST | `/tasks` | Create a task from `{"title": "..."}`, `400` if title missing/empty |
| Update | PUT | `/tasks/{id}` | Update `title` and/or `done`, `404`/`400` on error |
| Delete | DELETE | `/tasks/{id}` | Delete a task → `204 No Content`, `404` if unknown |
| Extra | GET | `/stats` | `{"total", "done", "open"}` computed with `COUNT(*)` in SQL |
| Extra | POST | `/reset` | Wipes and re-seeds the 3 example tasks |

Status codes: `200` reads, `201` create, `204` delete, `400` invalid body,
`404` unknown id — every error returns `{"error": "..."}`.

All queries use **parameterized placeholders** (`%s`, psycopg's style) —
no user input is ever glued directly into a SQL string.

## Proof the API didn't change

The same curl commands from the A1 and A2 READMEs still work identically
here — same requests, same responses, same status codes. Only `db.py`
was rewritten; `main.py`'s routes are untouched. That's what "storage is
just an implementation detail" means in practice: the client genuinely
cannot tell whether tasks live in a Python list, a SQLite file, or a
Postgres server.

## Testing with curl

```bash
curl -i http://localhost:8000/tasks
curl -i http://localhost:8000/tasks/1
curl -i http://localhost:8000/tasks/999                          # 404

curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" -d '{"title":"Buy milk"}'  # 201

curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" -d '{}'                    # 400

curl -i -X PUT http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" -d '{"done": true}'        # 200

curl -i -X DELETE http://localhost:8000/tasks/1                  # 204
```

Verified sample output (from this build):

```
$ curl -i http://localhost:8000/tasks/1
HTTP/1.1 200 OK
content-type: application/json

{"id":1,"title":"Buy milk","done":false}
```

### Proving persistence across a full stack restart

```bash
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Persisted task"}'
docker compose down
docker compose up
curl http://localhost:8000/tasks
# "Persisted task" is still there — the named volume kept the Postgres data
# even though both containers were fully removed and recreated.
```

## Looking at the data directly

```bash
docker exec -it taskdb psql -U postgres -d tasks
```
(if you're using Compose instead of a hand-run container, find the container name with `docker ps` first — it'll be something like `crud-api-db-1`)

Inside `psql`:
```sql
\dt                          -- list tables
SELECT * FROM tasks;
SELECT * FROM tasks WHERE done = true;
\q                            -- quit
```

*(Insert your psql/DB screenshot here.)*

Any change made here shows up immediately through `GET /tasks` — the API
and `psql` are reading the exact same database, no syncing involved.

## The mortality experiment, database edition

Run Postgres **without** a volume, create a few tasks, then `docker rm`
the container and start a fresh one — the data is gone, because nothing
outside the container kept it. The `taskdata` volume in `compose.yaml` is
what prevents that: it lives outside the container's lifecycle, so
`docker compose down` (without `-v`) and `up` again leaves your rows
untouched.

## Notes for your submission

- Same public GitHub repo as Assignments 1 and 2 — this is a continuation.
- `.env` never appears in git history — only `.env.example` is committed.
- Commit per stage (`git add . && git commit -m "Stage N: ..."`).
- Confirm a clean clone works: `cp .env.example .env && docker compose up`
  should give a fully working API with no manual database setup.
- Add your `psql`/DB screenshot to this README before submitting.

Swagger UI screenshot (Assignment 1):

<img width="1918" height="932" alt="Screenshot 2026-07-18 194259" src="https://github.com/user-attachments/assets/b02a1ed7-2109-476d-b3f6-4f71594895e1" />

<img width="1918" height="932" alt="Screenshot 2026-07-24 125259" src="https://github.com/user-attachments/assets/b02a1ed7-2109-476d-b3f6-4f71594895e1" />
