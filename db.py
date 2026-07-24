"""
db.py — the single module that talks to the database.

Every other file (main.py) only calls functions from here. This is the
"repository" the assignment describes: if storage ever changes again,
this is the only file that should need to change.

Connects to Postgres using the DATABASE_URL environment variable (read
from a .env file via python-dotenv), creates the tasks table if it's
missing, and seeds 3 example tasks only the first time the table is empty.
"""

import os
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()  # reads .env into the environment, if present

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:dev@localhost:5432/tasks"
)


def get_connection() -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


def init_db() -> None:
    """Create the tasks table if missing, and seed 3 tasks only if empty."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        done BOOLEAN NOT NULL DEFAULT FALSE
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks (title)")

                cur.execute("SELECT COUNT(*) AS count FROM tasks")
                count = cur.fetchone()["count"]

                if count == 0:
                    cur.executemany(
                        "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                        [
                            ("Buy milk", False),
                            ("Write README", False),
                            ("Push to GitHub", True),
                        ],
                    )
    finally:
        conn.close()


def ping() -> bool:
    """Used by the /health endpoint to confirm the database is reachable."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    finally:
        conn.close()


def list_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list:
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list = []

    if done is not None:
        query += " AND done = %s"
        params.append(done)

    if search:
        query += " AND title ILIKE %s"
        params.append(f"%{search}%")

    query += " ORDER BY title"

    if limit is not None:
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset or 0])

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()


def get_task(task_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            return cur.fetchone()
    finally:
        conn.close()


def create_task(title: str) -> dict:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING *",
                    (title, False),
                )
                return cur.fetchone()
    finally:
        conn.close()


def update_task(task_id: int, title: str, done: bool) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET title = %s, done = %s WHERE id = %s RETURNING *",
                    (title, done, task_id),
                )
                return cur.fetchone()
    finally:
        conn.close()


def delete_task(task_id: int) -> bool:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                return cur.rowcount > 0
    finally:
        conn.close()


def stats() -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM tasks")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS done FROM tasks WHERE done = TRUE")
            done_count = cur.fetchone()["done"]
        return {"total": total, "done": done_count, "open": total - done_count}
    finally:
        conn.close()


def reset() -> list:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks")
                cur.executemany(
                    "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                    [
                        ("Buy milk", False),
                        ("Write README", False),
                        ("Push to GitHub", True),
                    ],
                )
                cur.execute("SELECT * FROM tasks ORDER BY id")
                return cur.fetchall()
    finally:
        conn.close()