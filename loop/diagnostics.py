from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import traceback
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


DIAGNOSTIC_SCHEMA = "loop-exception/v1"
_MAX_TEXT_LENGTH = 4000
_SECRET_KEY_RE = re.compile(
    r"(?i)(token|secret|password|passwd|api[_-]?key|authorization|cookie|webhook)"
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key|authorization|cookie|webhook)"
    r"(\s*[:=]\s*)([^,\s;\}\]]+)"
)
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s,;]+")
_WEBHOOK_URL_RE = re.compile(
    r"(?i)(https?://[^/\s]+/rest/[^/\s]+/)[^/\s?#]+"
)


def _redact_text(value: str) -> str:
    text = value
    text = _WEBHOOK_URL_RE.sub(r"\1<redacted>", text)
    text = _BEARER_RE.sub(r"\1<redacted>", text)
    text = _SECRET_VALUE_RE.sub(r"\1\2<redacted>", text)
    if len(text) > _MAX_TEXT_LENGTH:
        return text[:_MAX_TEXT_LENGTH] + "…<truncated>"
    return text


def _redact(value: Any, *, key: str = "") -> Any:
    if _SECRET_KEY_RE.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(item_key): _redact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _redact_text(str(value))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def capture_exception(
    exc: BaseException,
    *,
    operation: str,
    project_root: Path | str | None = None,
    context: Mapping[str, Any] | None = None,
    stream: TextIO | None = None,
) -> dict[str, Any]:
    """Persist one redacted exception report and return its machine-readable receipt."""

    error_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "schema": DIAGNOSTIC_SCHEMA,
        "error_id": error_id,
        "timestamp": timestamp,
        "operation": operation,
        "exception": {
            "type": type(exc).__name__,
            "message": _redact_text(str(exc)),
            "traceback": _redact_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))),
        },
        "context": _redact(context or {}),
    }
    exception_metadata = {
        name: getattr(exc, name)
        for name in ("method", "status_code", "url")
        if getattr(exc, name, None) is not None
    }
    if exception_metadata:
        report["exception"]["metadata"] = _redact(exception_metadata)

    latest_path: Path | None = None
    journal_path: Path | None = None
    if project_root is not None:
        root = Path(project_root).expanduser().resolve()
        diagnostics_dir = root / ".loop" / "diagnostics"
        latest_path = diagnostics_dir / "last-exception.json"
        journal_path = diagnostics_dir / "exceptions.jsonl"
        report["diagnostic_path"] = str(latest_path)
        report["journal_path"] = str(journal_path)
        try:
            _append_jsonl(journal_path, report)
            _atomic_write(
                latest_path,
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
            )
        except Exception as persist_exc:
            report["persistence_error"] = _redact_text(str(persist_exc))

    target = stream if stream is not None else sys.stderr
    target.write(
        f"loop exception [{error_id}] {operation}: {type(exc).__name__}: {_redact_text(str(exc))}\n"
    )
    if latest_path is not None:
        target.write(f"  diagnostic: {latest_path}\n")
    target.flush()
    return report
