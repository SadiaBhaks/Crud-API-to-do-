"""
Task API — a small in-memory CRUD API for the FlyRank Backend Track W2/A1 assignment.

Run with:
    uvicorn main:app --reload --port 8000

Then open:
    http://localhost:8000/          (API description)
    http://localhost:8000/health    (health check)
    http://localhost:8000/docs      (Swagger UI)
"""

from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small in-memory to-do list API — full CRUD, built for FlyRank W2 A1.",
)

# ---------------------------------------------------------------------------
# In-memory "database" — a plain Python list. Data resets every restart.
# ---------------------------------------------------------------------------

DEFAULT_TASKS = [
    {"id": 1, "title": "Buy milk", "done": False},
    {"id": 2, "title": "Write README", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": True},
]

tasks: List[dict] = [dict(t) for t in DEFAULT_TASKS]
next_id = 4  # next free id to hand out


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if v is None or not v.strip():
            raise ValueError("title must not be empty")
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def title_not_blank_if_present(cls, v):
        if v is not None and not v.strip():
            raise ValueError("title must not be empty")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_task(task_id: int) -> Optional[dict]:
    return next((t for t in tasks if t["id"] == task_id), None)


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


# ---------------------------------------------------------------------------
# Stage 1 — root & health
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Stage 2 — read (list + single), with stretch: filter / search / stats
# ---------------------------------------------------------------------------

@app.get("/tasks")
def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
):
    result = tasks

    if done is not None:
        result = [t for t in result if t["done"] == done]

    if search:
        needle = search.lower()
        result = [t for t in result if needle in t["title"].lower()]

    if offset:
        result = result[offset:]
    if limit is not None:
        result = result[:limit]

    return result


@app.get("/stats")
def stats():
    total = len(tasks)
    done_count = sum(1 for t in tasks if t["done"])
    return {"total": total, "done": done_count, "open": total - done_count}


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return error(404, f"Task {task_id} not found")
    return task


# ---------------------------------------------------------------------------
# Stage 3 — create
# ---------------------------------------------------------------------------

@app.post("/tasks", status_code=201)
def create_task(payload: dict):
    title = payload.get("title") if isinstance(payload, dict) else None
    if not title or not str(title).strip():
        return error(400, "title is required and must not be empty")

    global next_id
    task = {"id": next_id, "title": str(title).strip(), "done": False}
    tasks.append(task)
    next_id += 1
    return JSONResponse(status_code=201, content=task)


# ---------------------------------------------------------------------------
# Stage 4 — update & delete
# ---------------------------------------------------------------------------

@app.put("/tasks/{task_id}")
def update_task(task_id: int, payload: dict):
    task = find_task(task_id)
    if task is None:
        return error(404, f"Task {task_id} not found")

    if not isinstance(payload, dict) or not payload:
        return error(400, "request body must include title and/or done")

    if "title" in payload:
        new_title = payload["title"]
        if not new_title or not str(new_title).strip():
            return error(400, "title must not be empty")
        task["title"] = str(new_title).strip()

    if "done" in payload:
        if not isinstance(payload["done"], bool):
            return error(400, "done must be true or false")
        task["done"] = payload["done"]

    return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return error(404, f"Task {task_id} not found")
    tasks.remove(task)
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Stretch — seed & reset (handy for demos / the "mortality experiment")
# ---------------------------------------------------------------------------

@app.post("/reset")
def reset_tasks():
    global tasks, next_id
    tasks = [dict(t) for t in DEFAULT_TASKS]
    next_id = 4
    return {"status": "reset", "tasks": tasks}