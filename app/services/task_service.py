import asyncio
import json
import logging
import sqlite3
import traceback
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Awaitable, Callable

from app.models.schemas import (
    TaskCreateResponse,
    TaskDetail,
    TaskListResponse,
    TaskStatus,
    TaskSummary,
    TaskType,
)

logger = logging.getLogger(__name__)

DB_PATH = Path("data/task_center.db")
_DB_LOCK = Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_column(conn: sqlite3.Connection, column_name: str, definition: str) -> None:
    cursor = conn.execute("PRAGMA table_info(tasks)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {definition}")


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    input_payload TEXT NOT NULL,
                    result_payload TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            _ensure_column(conn, "retry_count", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(conn, "max_retries", "INTEGER NOT NULL DEFAULT 0")
            conn.commit()


def _execute(query: str, params: tuple[Any, ...] = ()) -> None:
    _ensure_db()
    with _DB_LOCK:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(query, params)
            conn.commit()


def _fetchone(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    _ensure_db()
    with _DB_LOCK:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return cursor.fetchone()


def _fetchall(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    _ensure_db()
    with _DB_LOCK:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return cursor.fetchall()


def _decode_json(value: str) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def create_task(
    task_type: TaskType,
    input_payload: dict[str, Any],
    message: str,
    max_retries: int = 0,
) -> TaskCreateResponse:
    task_id = str(uuid.uuid4())
    now = _utc_now()
    _execute(
        """
        INSERT INTO tasks (
            task_id, task_type, status, message, input_payload, result_payload, error,
            retry_count, max_retries, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            task_type,
            "pending",
            message,
            json.dumps(input_payload, ensure_ascii=False),
            "",
            "",
            0,
            max_retries,
            now,
            now,
        ),
    )
    logger.info("Created task %s type=%s max_retries=%s", task_id, task_type, max_retries)
    return TaskCreateResponse(task_id=task_id, status="pending", message=message)


def update_task_status(
    task_id: str,
    status: TaskStatus,
    message: str,
    result: dict[str, Any] | None = None,
    error: str = "",
    retry_count: int | None = None,
) -> None:
    current = get_task(task_id)
    if current is None:
        return

    _execute(
        """
        UPDATE tasks
        SET status = ?, message = ?, result_payload = ?, error = ?, retry_count = ?, updated_at = ?
        WHERE task_id = ?
        """,
        (
            status,
            message,
            json.dumps(result, ensure_ascii=False) if result is not None else (json.dumps(current.result, ensure_ascii=False) if current.result is not None else ""),
            error,
            current.retry_count if retry_count is None else retry_count,
            _utc_now(),
            task_id,
        ),
    )


def get_task(task_id: str) -> TaskDetail | None:
    row = _fetchone("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if row is None:
        return None
    return TaskDetail(
        task_id=row["task_id"],
        task_type=row["task_type"],
        status=row["status"],
        message=row["message"],
        retry_count=row["retry_count"],
        max_retries=row["max_retries"],
        input_payload=_decode_json(row["input_payload"]),
        result=_decode_json(row["result_payload"]) if row["result_payload"] else None,
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_tasks(limit: int = 20) -> TaskListResponse:
    rows = _fetchall(
        "SELECT task_id, task_type, status, message, retry_count, max_retries, created_at, updated_at FROM tasks "
        "ORDER BY datetime(created_at) DESC LIMIT ?",
        (limit,),
    )
    items = [
        TaskSummary(
            task_id=row["task_id"],
            task_type=row["task_type"],
            status=row["status"],
            message=row["message"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
    return TaskListResponse(items=items, count=len(items))


async def _run_task(
    task_id: str,
    runner: Callable[[], Awaitable[dict[str, Any]]],
    running_message: str,
    success_message: str,
    max_retries: int,
    retry_delay_seconds: float,
) -> None:
    attempt = 0
    update_task_status(task_id, "running", running_message, retry_count=attempt)
    logger.info("Task %s started", task_id)

    while True:
        try:
            result = await runner()
            update_task_status(
                task_id,
                "succeeded",
                success_message,
                result=result,
                error="",
                retry_count=attempt,
            )
            logger.info("Task %s succeeded after %s retries", task_id, attempt)
            return
        except Exception as exc:
            attempt += 1
            error_text = f"{exc}\n\n{traceback.format_exc()}"
            logger.exception("Task %s failed on attempt %s/%s", task_id, attempt, max_retries + 1)

            if attempt > max_retries:
                update_task_status(
                    task_id,
                    "failed",
                    "任务执行失败，已达到最大重试次数",
                    error=error_text,
                    retry_count=attempt - 1,
                )
                return

            update_task_status(
                task_id,
                "running",
                f"任务失败，正在进行第 {attempt} 次重试",
                error=error_text,
                retry_count=attempt,
            )
            await asyncio.sleep(retry_delay_seconds)


def schedule_task(
    task_id: str,
    runner: Callable[[], Awaitable[dict[str, Any]]],
    running_message: str,
    success_message: str,
    max_retries: int = 0,
    retry_delay_seconds: float = 2.0,
) -> None:
    logger.info(
        "Scheduling task %s with max_retries=%s retry_delay_seconds=%s",
        task_id,
        max_retries,
        retry_delay_seconds,
    )
    asyncio.create_task(
        _run_task(
            task_id=task_id,
            runner=runner,
            running_message=running_message,
            success_message=success_message,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
    )
