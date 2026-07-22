# Task API

A to-do list API — full CRUD, now backed by a real **SQLite** database.
Built for the FlyRank Internship Backend Track (Assignment 1 → Assignment 2).

Built with **Python 3 + FastAPI + sqlite3** (Python's built-in database
library — nothing extra to install for the database itself).

## Why SQLite

SQLite was chosen because it's a single file (`tasks.db`) with no separate
server to install, configure, or run — you just open the file and it exists.
That makes it perfect for a small project like this: zero setup, and the
whole database can be copied, backed up, or inspected just like any other
file. The tradeoff (which is fine here) is that SQLite isn't built for many
simultaneous writers hammering it at once — that's when a project graduates
to something like Postgres.

## Where the database lives

`tasks.db` sits next to `main.py`, and is created automatically the first
time you run the app — the `tasks` table and its 3 seed rows are created
only if they don't already exist, so restarting never duplicates them.

`tasks.db` is **git-ignored** (see `.gitignore`) so every fresh clone starts
from a clean, freshly-seeded database rather than shipping the maintainer's
personal data.

## How to run it

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open:
- `http://localhost:8000/` — API description
- `http://localhost:8000/health` — health check
- `http://localhost:8000/docs` — **Swagger UI**

## Endpoints

Identical to Assignment 1 — only the storage underneath changed, from a
Python list to SQL queries against `tasks.db`.

| CRUD | Method | Path | Description |
|------|--------|------|-------------|
| — | GET | `/` | API description |
| — | GET | `/health` | Health check → `{"status": "ok"}` |
| Read | GET | `/tasks` | List all tasks (supports `?done=`, `?search=`, `?limit=`, `?offset=`) |
| Read | GET | `/tasks/{id}` | Get one task, or `404` if it doesn't exist |
| Create | POST | `/tasks` | Create a task from `{"title": "..."}`, `400` if title missing/empty |
| Update | PUT | `/tasks/{id}` | Update `title` and/or `done`, `404`/`400` on error |
| Delete | DELETE | `/tasks/{id}` | Delete a task → `204 No Content`, `404` if unknown |
| Extra | GET | `/stats` | `{"total", "done", "open"}` computed with `COUNT(*)` in SQL |
| Extra | POST | `/reset` | Wipes and re-seeds the 3 example tasks |

Status codes: `200` reads, `201` create, `204` delete, `400` invalid body,
`404` unknown id — every error returns `{"error": "..."}`.

All queries use **parameterized placeholders** (`?`) — no user input is
ever glued directly into a SQL string, which is what keeps the database
safe from SQL injection.

## Proof the API didn't change

Every curl command and status code from the Assignment 1 README still
works exactly the same against this version — same requests, same
responses. That's the entire point of separating the API from its
storage: the client can't tell whether tasks live in a Python list or a
SQLite file. If any of these tests had needed to change, that would mean
the storage swap had leaked into the API — which it didn't.

## Testing with curl

```bash
# Read
curl -i http://localhost:8000/tasks
curl -i http://localhost:8000/tasks/1
curl -i http://localhost:8000/tasks/999                          # 404

# Create
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" -d '{"title":"Buy milk"}'  # 201

curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" -d '{}'                    # 400

# Update
curl -i -X PUT http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" -d '{"done": true}'        # 200

# Delete
curl -i -X DELETE http://localhost:8000/tasks/1                  # 204
```

Verified sample output (from this build):

```
$ curl -i http://localhost:8000/tasks/1
HTTP/1.1 200 OK
content-type: application/json

{"id":1,"title":"Buy milk","done":true}
```

### Proving persistence

```bash
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Persisted task"}'
# stop the server (Ctrl+C), then start it again:
uvicorn main:app --reload --port 8000
curl http://localhost:8000/tasks
# "Persisted task" is still there — this never happened in Assignment 1.
```

## Exploring the database with DB Browser for SQLite

1. Install [DB Browser for SQLite](https://sqlitebrowser.org/) (free).
2. Open `tasks.db` from this project folder.
3. Go to the **Browse Data** tab — you'll see the `tasks` table laid out
   like a spreadsheet, the same rows your API serves.
4. Go to **Execute SQL** and try, one at a time:

```sql
SELECT * FROM tasks;                        -- list every task
SELECT * FROM tasks WHERE done = 1;         -- only completed tasks
SELECT COUNT(*) FROM tasks;                 -- how many tasks are there?
```

Example run: `SELECT * FROM tasks WHERE done = 1;` returned 2 rows —
`Buy milk` and `Push to GitHub` — matching exactly what `GET
/tasks?done=true` returns through the API. Any change made here (an
`UPDATE` or `DELETE`) shows up immediately through `GET /tasks` with no
server restart, because the API and DB Browser are reading the exact same
file — there's no syncing, just one source of truth.

*(Insert your DB Browser screenshot here.)*

## The mortality experiment — resolved

In Assignment 1, restarting the server wiped every task. Now: create a
task, restart the server, `GET /tasks` — it's still there. That's the
whole upgrade this assignment makes: the API's promise (create/read/
update/delete tasks) now survives past the life of the running process,
because the data lives on disk in `tasks.db` instead of in a variable in
memory.

## Notes for your submission

## Notes for your submission

- Same public GitHub repo as Assignment 1 — this is a continuation, not a
  new project.
- Commit per stage (`git add . && git commit -m "Stage N: ..."`).
- Push, then confirm a clean clone (or deleting `tasks.db` and restarting)
  still gives you 3 seeded tasks automatically.
- Add your DB Browser screenshot and the SQL query output to this README
  before submitting.

Swagger UI screenshot (Assignment 1):

<img width="1918" height="932" alt="Screenshot 2026-07-18 194259" src="https://github.com/user-attachments/assets/b02a1ed7-2109-476d-b3f6-4f71594895e1" />