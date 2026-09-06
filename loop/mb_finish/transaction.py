"""Sidecar finish transaction journal for mb-finish (T-HUB-068).

States:
  prepared -> context_written -> index_written -> committed
  Failure at any stage -> rollback_required

Schema: loop-finish-transaction/v1
Sidecar path: .claude/runtime/epic/finish-tx.json
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.hooks.epic.core import atomic_write_text

FINISH_TX_SCHEMA: str = "loop-finish-transaction/v1"
SIDECAR_REL_PATH: str = ".claude/runtime/epic/finish-tx.json"


class FinishTxState(str, Enum):
    PREPARED = "prepared"
    CONTEXT_WRITTEN = "context_written"
    INDEX_WRITTEN = "index_written"
    COMMITTED = "committed"
    ROLLBACK_REQUIRED = "rollback_required"


class FinishTxStagedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rel_path: str
    stage_path: str
    backup_path: str | None = None


class FinishTxRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["loop-finish-transaction/v1"] = Field(
        default=FINISH_TX_SCHEMA, alias="schema"
    )
    tx_id: str
    epic_id: str
    step_id: str
    phase: str
    state: FinishTxState
    staged_files: list[FinishTxStagedFile] = Field(default_factory=list)
    recovery_token: str | None = None
    error: str | None = None


def get_finish_tx_path(cwd: Path | str) -> Path:
    """Return the filesystem path for the finish transaction journal sidecar."""
    return Path(cwd) / SIDECAR_REL_PATH


def read_finish_tx(cwd: Path | str) -> FinishTxRecord | None:
    """Read and validate the finish transaction journal sidecar if it exists."""
    tx_file = get_finish_tx_path(cwd)
    if not tx_file.exists():
        return None
    raw = json.loads(tx_file.read_text(encoding="utf-8"))
    return FinishTxRecord.model_validate(raw)


def write_finish_tx(cwd: Path | str, record: FinishTxRecord) -> None:
    """Write the finish transaction journal sidecar atomically with schema validation."""
    tx_file = get_finish_tx_path(cwd)
    tx_file.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(by_alias=True, mode="json")
    atomic_write_text(tx_file, json.dumps(payload, indent=2))


FinishTransaction = FinishTxRecord
begin_finish_transaction = write_finish_tx


def validate_identity(
    staged_epic_id: str,
    staged_step_id: str,
    index_target_step_id: str,
    armed_epic_id: str,
    armed_step_id: str,
) -> bool:
    """Check identity match between staged Handoff, index target, and armed state.

    FR-004 / TM-006: Staged Handoff epic_id/step_id == index target == state armed.
    """
    if staged_epic_id != armed_epic_id:
        return False
    if staged_step_id != armed_step_id:
        return False
    if index_target_step_id != armed_step_id:
        return False
    return True


def stage_file_in_tx(
    cwd: Path | str,
    tx_id: str,
    rel_path: str,
    content: str,
) -> FinishTxStagedFile:
    """Stage a file in the transaction working directory."""
    cwd_path = Path(cwd)
    tx_dir = cwd_path / ".claude" / "runtime" / "epic" / "tx" / tx_id
    tx_dir.mkdir(parents=True, exist_ok=True)

    stage_file = tx_dir / Path(rel_path).name
    atomic_write_text(stage_file, content)

    target_file = cwd_path / rel_path
    backup_file: Path | None = None
    if target_file.exists():
        backup_dir = tx_dir / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / Path(rel_path).name
        atomic_write_text(backup_file, target_file.read_text(encoding="utf-8"))

    return FinishTxStagedFile(
        rel_path=rel_path,
        stage_path=str(stage_file.relative_to(cwd_path)),
        backup_path=str(backup_file.relative_to(cwd_path)) if backup_file else None,
    )


def commit_staged_files(cwd: Path | str, staged_files: list[FinishTxStagedFile]) -> None:
    """Replace target files with staged files atomically (fsync + replace via atomic_write_text)."""
    cwd_path = Path(cwd)
    for sf in staged_files:
        stage_file = cwd_path / sf.stage_path
        target_file = cwd_path / sf.rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        content = stage_file.read_text(encoding="utf-8")
        atomic_write_text(target_file, content)


def rollback_staged_files(cwd: Path | str, staged_files: list[FinishTxStagedFile]) -> None:
    """Rollback target files from backup or remove if newly created."""
    cwd_path = Path(cwd)
    for sf in staged_files:
        target_file = cwd_path / sf.rel_path
        if sf.backup_path:
            backup_file = cwd_path / sf.backup_path
            if backup_file.exists():
                atomic_write_text(target_file, backup_file.read_text(encoding="utf-8"))
        else:
            if target_file.exists():
                try:
                    target_file.unlink()
                except OSError:
                    pass


def cleanup_finish_tx(cwd: Path | str) -> None:
    """Remove sidecar finish-tx.json file."""
    tx_file = get_finish_tx_path(cwd)
    if tx_file.exists():
        try:
            tx_file.unlink()
        except OSError:
            pass


def recover_finish_transaction(cwd: Path | str) -> dict[str, Any]:
    """Recover leftover finish transaction journal sidecar or repair mixed identity.

    States:
    - committed: delete leftover journal sidecar; state is already consistent.
    - index_written: all files staged & written, complete the commit transition.
    - context_written / prepared / rollback_required: roll back any staged files & restore backups.
    - corrupt journal: fail-closed NEED_HUMAN.
    """
    cwd_path = Path(cwd)
    tx_file = get_finish_tx_path(cwd_path)
    if tx_file.exists():
        try:
            rec = read_finish_tx(cwd_path)
        except Exception as exc:
            return {
                "ok": False,
                "halt": True,
                "stop": "NEED_HUMAN",
                "diagnostic_code": "corrupt_finish_transaction_journal",
                "reason": f"NEED_HUMAN: Corrupt finish transaction journal at {tx_file}: {exc}",
            }

        if rec is not None:
            if rec.state == FinishTxState.COMMITTED:
                cleanup_finish_tx(cwd_path)
                return {"ok": True, "recovered": True, "state": rec.state.value, "action": "cleaned_committed"}
            elif rec.state == FinishTxState.INDEX_WRITTEN:
                # Crash after index before committed marker: commit remainder and mark clean
                commit_staged_files(cwd_path, rec.staged_files)
                cleanup_finish_tx(cwd_path)
                return {"ok": True, "recovered": True, "state": rec.state.value, "action": "committed_remainder"}
            else:
                # context_written / prepared / rollback_required: rollback
                rollback_staged_files(cwd_path, rec.staged_files)
                cleanup_finish_tx(cwd_path)
                return {"ok": True, "recovered": True, "state": rec.state.value, "action": "rolled_back"}

    return {"ok": True, "recovered": False, "reason": "no_journal"}

