"""
Task API — now backed by a real SQLite database (tasks.db) instead of
an in-memory list. Same endpoints, same request/response shapes as
Assignment 1 — only the storage layer changed.

Run with:
    uvicorn main:app --reload --port 8000

Then open:
    http://localhost:8000/          (API description)
    http://localhost:8000/health    (health check)
    http://localhost:8000/docs      (Swagger UI)

tasks.db is created automatically the first time you run this, in the
same folder as main.py. It's git-ignored, so every fresh clone starts
with a clean database seeded with 3 example tasks.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Task API",
    version="2.0",
    description="A SQLite-backed to-do list API — full CRUD, built for FlyRank W3 A2.",
)

DB_PATH = Path(__file__).parent / "tasks.db"


# ---------------------------------------------------------------------------
# Database setup — Stage 0
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # helps the search/filter extras (WHERE title LIKE ..., WHERE done = ...)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title)")

        # Seed only if the table is empty — a transaction so it's all-or-nothing.
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            with conn:  # commits automatically, rolls back on error
                conn.executemany(
                    "INSERT INTO tasks (title, done) VALUES (?, ?)",
                    [
                        ("Buy milk", 0),
                        ("Write README", 0),
                        ("Push to GitHub", 1),
                    ],
                )
        else:
            conn.commit()
    finally:
        conn.close()


init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def row_to_task(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


# ---------------------------------------------------------------------------
# Stage: root & health (unchanged from A1)
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"name": "Task API", "version": "2.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stage 1 — read from the database
# ---------------------------------------------------------------------------

@app.get("/tasks")
def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
):
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list = []

    if done is not None:
        query += " AND done = ?"
        params.append(1 if done else 0)

    if search:
        query += " AND title LIKE ?"
        params.append(f"%{search}%")

    query += " ORDER BY title"

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset or 0])

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    return [row_to_task(r) for r in rows]


@app.get("/stats")
def stats():
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
    finally:
        conn.close()
    return {"total": total, "done": done_count, "open": total - done_count}


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return error(404, "Task not found")
    return row_to_task(row)


# ---------------------------------------------------------------------------
# Stage 2 — create (INSERT)
# ---------------------------------------------------------------------------

@app.post("/tasks", status_code=201)
def create_task(payload: dict):
    title = payload.get("title") if isinstance(payload, dict) else None
    if not title or not str(title).strip():
        return error(400, "title is required and must not be empty")

    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, done) VALUES (?, ?)",
                (str(title).strip(), 0),
            )
        new_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()
    finally:
        conn.close()

    return JSONResponse(status_code=201, content=row_to_task(row))


# ---------------------------------------------------------------------------
# Stage 3 — update & delete (UPDATE / DELETE)
# ---------------------------------------------------------------------------

@app.put("/tasks/{task_id}")
def update_task(task_id: int, payload: dict):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return error(404, "Task not found")

        if not isinstance(payload, dict) or not payload:
            return error(400, "request body must include title and/or done")

        new_title = row["title"]
        new_done = row["done"]

        if "title" in payload:
            if not payload["title"] or not str(payload["title"]).strip():
                return error(400, "title must not be empty")
            new_title = str(payload["title"]).strip()

        if "done" in payload:
            if not isinstance(payload["done"], bool):
                return error(400, "done must be true or false")
            new_done = 1 if payload["done"] else 0

        with conn:
            conn.execute(
                "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
                (new_title, new_done, task_id),
            )
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()

    return row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return error(404, "Task not found")
        with conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    finally:
        conn.close()
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Reset — handy for demos (re-seeds if table is emptied)
# ---------------------------------------------------------------------------

@app.post("/reset")
def reset_tasks():
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM tasks")
            conn.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)",
                [
                    ("Buy milk", 0),
                    ("Write README", 0),
                    ("Push to GitHub", 1),
                ],
            )
        rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()
    return {"status": "reset", "tasks": [row_to_task(r) for r in rows]}