"""Task-board client abstractions for local synchronization and tests."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import httpx

from loop.board_launch.loop_run import ExecutionResult

from .diff import BoardTask


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """Bounded, observational result of one board-card loop execution."""

    task_id: str
    status: str
    exit_code: int | None
    diagnostic_code: str | None = None
    log_path: str | None = None
    model_source: str | None = None
    model_env: str | None = None

    def payload(self) -> dict[str, Any]:
        return asdict(self)


_MAX_EXECUTION_LOG_PATH = 1_000


def execution_record(task_id: str, result: ExecutionResult) -> ExecutionRecord:
    """Normalize a launch result before sending it to the Host."""
    path = str(result.log_path) if result.log_path else None
    if path is not None:
        path = path[-_MAX_EXECUTION_LOG_PATH:]
    return ExecutionRecord(
        task_id=task_id,
        status=result.status,
        exit_code=result.exit_code,
        diagnostic_code=result.diagnostic_code,
        log_path=path,
        model_source=result.model_source,
        model_env=result.model_env,
    )


class BoardClientError(RuntimeError):
    """A task-board HTTP request failed without a safe fallback."""

    def __init__(
        self,
        status_code: int | None,
        body: str,
        *,
        lock_conflict: bool = False,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.lock_conflict = lock_conflict
        status = status_code if status_code is not None else "transport"
        super().__init__(f"task-board request failed ({status}): {body}")


class HttpHostClient:
    """Synchronous client for the DSH Host task-board HTTP API."""

    def __init__(
        self,
        host_url: str,
        proxy_token: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized = host_url.rstrip("/")
        self._client = httpx.Client(
            base_url=normalized,
            headers=self._headers(normalized, proxy_token),
            transport=transport,
        )

    def list_tasks(self) -> list[BoardTask]:
        payload = self._request("GET", "/api/task-board/state")
        raw_tasks = payload.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise BoardClientError(None, "task-board state tasks must be a list")
        try:
            return [_task_from_payload(task) for task in raw_tasks]
        except (KeyError, TypeError, ValueError) as exc:
            raise BoardClientError(None, f"invalid task-board state: {exc}") from exc

    def upsert(self, card: BoardTask) -> None:
        workspace_id = card.workspace_id or None
        if self._has_task(card.id):
            patch: dict[str, Any] = {
                "title": card.title,
                "description": card.description,
                "prompt": card.prompt,
            }
            if workspace_id:
                patch["workspaceId"] = workspace_id
            self._request(
                "POST",
                "/api/task-board/action",
                {"kind": "update", "taskId": card.id, "patch": patch},
            )
            return
        input_payload: dict[str, Any] = {
            "title": card.title,
            "description": card.description,
            "prompt": card.prompt,
        }
        if workspace_id:
            input_payload["workspaceId"] = workspace_id
        self._request(
            "POST",
            "/api/task-board/action",
            {"kind": "create", "id": card.id, "input": input_payload},
        )

    def archive(self, task_id: str) -> None:
        self._request(
            "POST",
            "/api/task-board/action",
            {"kind": "archive", "taskId": task_id},
        )

    def move(self, task_id: str, status: str) -> None:
        self._request(
            "POST",
            "/api/task-board/action",
            {"kind": "move", "taskId": task_id, "status": status},
        )

    def record_execution(self, record: ExecutionRecord) -> None:
        """Persist a single observational execution result for one task."""
        self._request(
            "POST",
            "/api/task-board/action",
            {
                "kind": "execution",
                "taskId": record.task_id,
                "execution": record.payload(),
            },
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _headers(host_url: str, proxy_token: str | None) -> dict[str, str]:
        headers = {
            "Origin": host_url,
            "Sec-Fetch-Site": "same-origin",
        }
        token = proxy_token or os.getenv("DSH_TASK_BOARD_PROXY_TOKEN")
        if token is None:
            return headers
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Proxy-Token"] = token
        headers["X-Dsh-Task-Board-Proxy-Token"] = token
        return headers

    def _has_task(self, task_id: str) -> bool:
        """Choose create/update from the current Host state, without fallback."""
        return any(task.id == task_id for task in self.list_tasks())

    def _request(
        self,
        method: str,
        path: str,
        action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        envelope = None
        if action is not None:
            envelope = {"requestId": str(uuid4()), "action": action}
        try:
            response = self._client.request(method, path, json=envelope)
        except httpx.HTTPError as exc:
            raise BoardClientError(None, str(exc)) from exc
        body = response.text
        if not 200 <= response.status_code < 300:
            raise BoardClientError(
                response.status_code,
                body,
                lock_conflict=_is_lock_conflict(response.status_code, body),
            )
        if not body:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise BoardClientError(response.status_code, body) from exc
        if not isinstance(payload, dict):
            raise BoardClientError(response.status_code, body)
        return payload


def _task_from_payload(payload: Any) -> BoardTask:
    if not isinstance(payload, dict):
        raise TypeError("task must be an object")
    return BoardTask(
        id=str(payload["id"]),
        title=str(payload.get("title", "")),
        description=str(payload.get("description", "")),
        prompt=str(payload.get("prompt", "")),
        workspace_id=str(payload.get("workspaceId") or payload.get("workspace_id", "")),
        status=str(payload.get("status", "todo")),
    )


def _is_lock_conflict(status_code: int, body: str) -> bool:
    if status_code == 409:
        return True
    lowered = body.lower()
    return "lock_conflict" in lowered or "lock conflict" in lowered


class TaskBoardClient(Protocol):
    """Minimal one-way task-board write interface."""

    def list_tasks(self) -> list[BoardTask]: ...

    def upsert(self, card: BoardTask) -> None: ...

    def archive(self, task_id: str) -> None: ...

    def move(self, task_id: str, status: str) -> None: ...

    def record_execution(self, record: ExecutionRecord) -> None: ...


class FakeClient:
    """In-memory board client with observable write accounting."""

    def __init__(self, tasks: list[BoardTask] | None = None) -> None:
        self.tasks: dict[str, BoardTask] = {task.id: task for task in tasks or []}
        self.archived: set[str] = set()
        self.moves: list[tuple[str, str]] = []
        self.execution_records: list[ExecutionRecord] = []
        self.write_count = 0

    def list_tasks(self) -> list[BoardTask]:
        return list(self.tasks.values())

    def upsert(self, card: BoardTask) -> None:
        self.tasks[card.id] = card
        self.archived.discard(card.id)
        self.write_count += 1

    def archive(self, task_id: str) -> None:
        if task_id in self.tasks:
            self.archived.add(task_id)
        self.write_count += 1

    def move(self, task_id: str, status: str) -> None:
        self.moves.append((task_id, status))
        if task_id in self.tasks:
            old_task = self.tasks[task_id]
            self.tasks[task_id] = BoardTask(
                id=old_task.id,
                title=old_task.title,
                description=old_task.description,
                prompt=old_task.prompt,
                workspace_id=old_task.workspace_id,
                status=status,
            )
        self.write_count += 1

    def record_execution(self, record: ExecutionRecord) -> None:
        """Keep the latest execution record separate from card projection."""
        self.execution_records.append(record)
        self.write_count += 1


class LedgerFileClient:
    """Offline JSON ledger client for CLI and integration tests."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.write_count = 0
        self.archived: set[str] = set()

    def list_tasks(self) -> list[BoardTask]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [BoardTask(**task) for task in payload.get("tasks", [])]

    def upsert(self, card: BoardTask) -> None:
        tasks = {task.id: task for task in self.list_tasks()}
        tasks[card.id] = card
        self._write(list(tasks.values()))

    def archive(self, task_id: str) -> None:
        self.archived.add(task_id)
        self.write_count += 1

    def move(self, task_id: str, status: str) -> None:
        tasks = {task.id: task for task in self.list_tasks()}
        if task_id in tasks:
            old_task = tasks[task_id]
            tasks[task_id] = BoardTask(
                id=old_task.id,
                title=old_task.title,
                description=old_task.description,
                prompt=old_task.prompt,
                workspace_id=old_task.workspace_id,
                status=status,
            )
            self._write(list(tasks.values()))

    def record_execution(self, record: ExecutionRecord) -> None:
        """Persist execution records without changing the task projection."""
        payload = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        records = payload.get("execution_records", [])
        if not isinstance(records, list):
            raise ValueError("offline ledger execution_records must be a list")
        records.append(record.payload())
        payload["execution_records"] = records
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.write_count += 1

    def _write(self, tasks: list[BoardTask]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"tasks": [asdict(task) for task in tasks]},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.write_count += 1
