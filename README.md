# Task API

A small in-memory to-do list API — full CRUD, built for the FlyRank Internship
Backend Track, Week 2, Assignment A1.

Built with **Python 3 + FastAPI**. Data lives in memory only (a plain Python
list) — restarting the server resets it to the three seed tasks.

## How to run it

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open:
- `http://localhost:8000/` — API description
- `http://localhost:8000/health` — health check
- `http://localhost:8000/docs` — **Swagger UI** (interactive docs, "Try it out")

## Endpoints

| CRUD | Method | Path | Description |
|------|--------|------|-------------|
| — | GET | `/` | API description |
| — | GET | `/health` | Health check → `{"status": "ok"}` |
| Read | GET | `/tasks` | List all tasks (supports `?done=`, `?search=`, `?limit=`, `?offset=`) |
| Read | GET | `/tasks/{id}` | Get one task, or `404` if it doesn't exist |
| Create | POST | `/tasks` | Create a task from `{"title": "..."}`, `400` if title missing/empty |
| Update | PUT | `/tasks/{id}` | Update `title` and/or `done`, `404`/`400` on error |
| Delete | DELETE | `/tasks/{id}` | Delete a task → `204 No Content`, `404` if unknown |
| Extra | GET | `/stats` | `{"total", "done", "open"}` counts |
| Extra | POST | `/reset` | Restores the 3 seed tasks |

Status codes used: `200` reads, `201` create, `204` delete, `400` invalid
body, `404` unknown id — every error returns `{"error": "..."}`.

## Testing with curl

```bash
# Read
curl -i http://localhost:8000/tasks
curl -i http://localhost:8000/tasks/1
curl -i http://localhost:8000/tasks/99          # 404

# Create
curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy milk"}'                      # 201

curl -i -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{}'                                        # 400

# Update
curl -i -X PUT http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"done": true}'                            # 200

# Delete
curl -i -X DELETE http://localhost:8000/tasks/1  # 204
curl -i -X DELETE http://localhost:8000/tasks/99 # 404
```

Sample verified output (from this build):

```
$ curl -i http://localhost:8000/tasks/1
HTTP/1.1 200 OK
content-type: application/json

{"id":1,"title":"Buy milk","done":false}
```

## Testing with Swagger UI

1. Start the server, then open `http://localhost:8000/docs`.
2. Every endpoint from the table above is listed, grouped by path.
3. Click any endpoint → **Try it out** → fill in the body/id → **Execute**.
4. Run the full cycle: `POST /tasks` a new task → `GET /tasks` to see it →
   `PUT /tasks/{id}` to mark it done → `DELETE /tasks/{id}` to remove it.
5. Take a screenshot of `/docs` for your submission.

## The mortality experiment

Create a few tasks, restart the server (`Ctrl+C` then run the `uvicorn`
command again), then `GET /tasks`. You'll see only the 3 seed tasks — every
task you created is gone. That's because everything lives in a Python list
in memory: as soon as the process stops, that memory is freed. This is
exactly why Week 3 introduces a real database.

## Notes for your submission

- Run `git init`, then commit once per stage (`git add . && git commit -m "Stage N: ..."`).
- Push to a public GitHub repo.
- Paste one `curl -i` output and a Swagger screenshot into this README before submitting.