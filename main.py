"""
Task API — now running against a real PostgreSQL database in Docker,
instead of SQLite. Same endpoints, same request/response shapes as
Assignment 1 and 2 — only the storage layer (db.py) changed again.

Run the whole stack with:
    docker compose up

Or run the app locally against a Postgres container started separately
(see README for both options).

Swagger UI: http://localhost:8000/docs
"""

from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import db

app = FastAPI(
    title="Task API",
    version="3.0",
    description="A Postgres-backed to-do list API — full CRUD, built for FlyRank W1 A3.",
)


@app.on_event("startup")
def on_startup():
    db.init_db()


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def row_to_task(row: dict) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


# ---------------------------------------------------------------------------
# Root & health (health now pings the database — a real production habit)
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"name": "Task API", "version": "3.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    try:
        db.ping()
        return {"status": "ok", "db": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "db": "unreachable"})


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@app.get("/tasks")
def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
):
    rows = db.list_tasks(done=done, search=search, limit=limit, offset=offset or 0)
    return [row_to_task(r) for r in rows]


@app.get("/stats")
def stats():
    return db.stats()


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    row = db.get_task(task_id)
    if row is None:
        return error(404, "Task not found")
    return row_to_task(row)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@app.post("/tasks", status_code=201)
def create_task(payload: dict):
    title = payload.get("title") if isinstance(payload, dict) else None
    if not title or not str(title).strip():
        return error(400, "title is required and must not be empty")

    row = db.create_task(str(title).strip())
    return JSONResponse(status_code=201, content=row_to_task(row))


# ---------------------------------------------------------------------------
# Update & delete
# ---------------------------------------------------------------------------

@app.put("/tasks/{task_id}")
def update_task(task_id: int, payload: dict):
    existing = db.get_task(task_id)
    if existing is None:
        return error(404, "Task not found")

    if not isinstance(payload, dict) or not payload:
        return error(400, "request body must include title and/or done")

    new_title = existing["title"]
    new_done = existing["done"]

    if "title" in payload:
        if not payload["title"] or not str(payload["title"]).strip():
            return error(400, "title must not be empty")
        new_title = str(payload["title"]).strip()

    if "done" in payload:
        if not isinstance(payload["done"], bool):
            return error(400, "done must be true or false")
        new_done = payload["done"]

    updated = db.update_task(task_id, new_title, new_done)
    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    existing = db.get_task(task_id)
    if existing is None:
        return error(404, "Task not found")
    db.delete_task(task_id)
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Reset — handy for demos
# ---------------------------------------------------------------------------

@app.post("/reset")
def reset_tasks():
    rows = db.reset()
    return {"status": "reset", "tasks": [row_to_task(r) for r in rows]}